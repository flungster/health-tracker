"""Data access objects.

Every database query in the application lives in this package. DAOs receive
their ``Session`` through the constructor (never created here), always scope
user data by ``user_id``, and always ignore soft-deleted rows.
"""
