# CouchCopy

CouchCopy is a command-line utility that live-copies a CouchDB database into another. Whilst CouchDB's native replication capability solves this problem for most cases, this tool is useful in situations where you explicitly want to ignore the rev history and only copy the "active" versions of a document. One example (and the original motivation for this tool) is if you have a lot of deleted conflicts in a database and need these to be removed without a purge operation.

# How it works

The tool essentially follows the CouchDB replication protocol except that instead of inserting the rev tree for each document found, it updates the target document with the current state of the source.

### Algorthm

1. Look for a checkpoint document on the source (to discover the last migrated change)
2. If checkpoint found, use that sequence number as the starting point (<seq>), else start from 0.
3. Get sourcedb/_changes?since_seq=<seq>&limit=<batch size>&include_docs=true
4. Extract the documents from the response
5. Get the set of document id/rev pairs for the document set from the target
6. For each document, update the _rev to match the target (or remove it if it doens't exist on the target)
7. Bulk insert (using _bulk_docs) on the target db
8. If successful, create a checkpoint on the source, storing the <last_seq> migrated
9. Go to 1.

### Future enhancements / limitations

* The current implementation does not support attachments
* Insertions could be parallelised
