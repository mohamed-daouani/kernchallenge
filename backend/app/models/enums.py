import enum

class UserRole(enum.Enum):
    admin = "admin"
    user = "user" 

class ProjectStatus(enum.Enum):
    active = "active"
    archived = "archived"