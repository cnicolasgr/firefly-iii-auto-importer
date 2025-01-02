from typing import List


class Configuration:
    def __init__(
        self,
        department: str = None,
        username: str = None,
        password: str | List[int] = None,
    ):
        self.department = department
        self.username = username
        self.password = password
