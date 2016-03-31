#!/usr/bin/python

import argparse
from cloudant import cloudant
import json

parser = argparse.ArgumentParser(description=
    'CouchCopy. Live-copy all documents between CouchDB databases, creating a new rev history')
parser.add_argument('username', type=str, help='username with read access to source and admin access to target')
parser.add_argument('password', type=str)
parser.add_argument('host', type=str, help='URL for host, e.g. https://myuser.cloudant.com')
parser.add_argument('source', type=str, help='source database name')
parser.add_argument('target', type=str, help='target database name')
parser.add_argument('--batchsize', type=int, default=500, help='number of documents to upload in each batch')
parser.add_argument('--batch', type=bool, default=True)

args = parser.parse_args()

checkpoint_name = '_local/couchcopy'

# In continuous mode just upload each change as it comes rather than batching.
# Batching would delay the writes until the batch is full.
if not args.batch:
    args.batchsize = 1


def print_metadata(label, db):
    print """{5}: {0}
Doc Count: {1}
Deleted Doc Count: {2}
Active Size: {3}
Disk Size: {4}
""".format(db['db_name'], db['doc_count'],
           db['doc_del_count'], db['sizes']['active'],
           db['sizes']['file'], label)


# Filter the sequence by elements with an 'error' field
def errors(seq):
    for el in seq:
        if 'error' in el:
            yield el


def upload_batch(last_change, batch, target_db):

    # return if nothing to upload
    if len(batch) == 0:
        print 'nothing to upload'
        return

    if 'seq' in last_change:
        seq = last_change['seq']
    else:
        seq = last_change['last_seq']

    print "uploading {0} docs at {1} ".format(len(batch), seq)

    # attempt to insert as new documents
    response = target_db.bulk_docs(batch)

    # reprocess any insertions that failed (i.e. the docs already exist)
    update_batch = []
    for error_doc in errors(response):
        if error_doc['error'] != 'conflict':
            raise Exception(error_doc)

        # match error to the source document
        source_doc = next(obj for obj in batch if obj['_id'] == error_doc['id'])

        try:
            # try again with the current rev
            target_doc = target_db[error_doc['id']]
            source_doc['_rev'] = target_doc['_rev']
            update_batch.append(source_doc)
        except KeyError:
            # document does not exist in the target
            if '_deleted' in source_doc:
                # no op - source and target are both deleted
                continue
            else:
                # should not happen
                raise

    target_db.bulk_docs(update_batch)

    # all done - checkpoint
    store_checkpoint(target_db, seq)


def store_checkpoint(db, seq):
    checkpoint = db[checkpoint_name]
    checkpoint['last_seq'] = seq
    checkpoint.save()


def get_checkpoint(db):
    try:
        checkpoint = db[checkpoint_name]
        print 'Checkpoint: found with since_seq {0}'.format(checkpoint['last_seq'])
        return checkpoint['last_seq']
    except KeyError:
        print 'Checkpoint: no checkpoint found'
        checkpoint = {'_id': checkpoint_name}
        checkpoint = db.create_document(checkpoint)
        return "0"


def go():
    with cloudant(args.username, args.password, url=args.host) as client:
        session = client.session()

        source_db = client[args.source]
        target_db = client[args.target]
        print_metadata("Source", source_db.metadata())
        print_metadata("Target", target_db.metadata())

        since_seq = get_checkpoint(target_db)

        batch = []

        for change in source_db.changes(since=since_seq,
                                        continuous=not args.batch,
                                        include_docs=True):

            if 'deleted' in change:
                batch.append({'_id': change['id'], '_deleted': True})
            elif 'doc' in change:
                # created or updated
                doc = change['doc']

                # we don't know whether the target contains this so assume create
                del doc['_rev']

                batch.append(doc)

                # attachments not supported - bail if we find one
                if '_attachments' in doc:
                    raise Exception("Cannot proceed - document has _attachments:\n" + json.dumps(doc))

            # If we reach the batch size, upload to the target
            if len(batch) == args.batchsize:
                upload_batch(change, batch, target_db)
                batch = []

        # Drain the batch
        upload_batch(change, batch, target_db)


# Run forever. Go() will finish when the _changes feed disconnects due to inactivity
while True:
    go()
