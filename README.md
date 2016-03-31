# CouchCopy

CouchCopy is a command-line utility that live-copies a CouchDB database into another. Whilst CouchDB's native replication capability solves this problem for most cases, this tool is useful in situations where you explicitly want to ignore the rev history and only copy the "active" versions of a document. One example (and the original motivation for this tool) is if you have a lot of deleted conflicts in a database and need these to be removed without a purge operation.

# How it works

The tool essentially follows the CouchDB replication protocol except that instead of inserting the rev tree for each document found, it updates the target document with the current state of the source.

# Assumptions

1. Nothing else is writing to the target database except this tool
2. There are no attachments to migrate

### Algorithm

1. Look for a checkpoint document on the target (to discover the last migrated change)
2. If checkpoint found, use that sequence number as the starting point (<seq>), else start from 0.
3. Get sourcedb/_changes?since_seq=<seq>&limit=<batch size>&include_docs=true
4. Extract the documents from the response and remove the _rev fields
5. Optimistically bulk insert (using _bulk_docs) on the target db.
6. For any inserts that failed, get their current _rev from the target and retry.
7. Create a checkpoint on the target, storing the last sequence number processed.
9. Go to 1.


### Future enhancements / limitations

* Add support for source/target on different hosts
* Add attachment support
* Insertions could be parallelised
