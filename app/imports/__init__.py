"""Excel/CSV import engine.

Flow (spec section 44): select file -> read workbook -> pick sheet -> map
columns -> preview -> validate -> user confirms -> commit -> log the batch.
Nothing here ever writes back to the source file (spec rule 55) - it is
opened read-only and only ever produces new database rows plus a logged
:class:`app.models.imports.ImportBatch`.
"""
