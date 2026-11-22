"""File importers: turn an uploaded file into geometry. They do not touch the database."""


class FileContentError(ValueError):
    """The file cannot be imported because of its content. The message is shown to the user as-is."""
