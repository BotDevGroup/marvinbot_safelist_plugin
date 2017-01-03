import mongoengine
# from telegram import User


class SafelistMember:
    def __init__(self, user, role):
        self.user = user
        self.role = role

    def get_role(self):
        return self.role

    def get_user(self):
        return self.user
