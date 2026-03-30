"""Custom exception hierarchy for PyxelQuest."""


class PyxelQuestError(Exception):
    """Base exception for all PyxelQuest errors."""


class DatabaseError(PyxelQuestError):
    """Raised when a database operation fails."""


class WorldGenerationError(PyxelQuestError):
    """Raised when world generation encounters an invalid state."""


class InvalidMoveError(PyxelQuestError):
    """Raised when a hero tries to move in a blocked direction."""


class CombatError(PyxelQuestError):
    """Raised when a combat operation is invalid."""


class InventoryFullError(PyxelQuestError):
    """Raised when adding an item to a full inventory (max 10)."""


class ItemNotFoundError(PyxelQuestError):
    """Raised when an item ID is not found in inventory or room."""


class GameNotFoundError(PyxelQuestError):
    """Raised when attempting to load a game that does not exist."""
