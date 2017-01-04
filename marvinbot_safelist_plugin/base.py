# -*- coding: utf-8 -*-
from marvinbot.utils import localized_date, get_message, trim_markdown, trim_accents
from marvinbot.handlers import CommonFilters, CommandHandler, MessageHandler
from marvinbot.plugins import Plugin
from marvinbot_safelist_plugin.models import SafelistMember
import logging
import threading
import hashlib

log = logging.getLogger(__name__)

WEREWOLF_SAFE_ROLES = [
    'normal villager',
    'lowly villager',
    'mason',
    'guardian angel',
    'fool',
    'mayor',
    'detective',
    'harlot',
    'beholder',
    'clumsy guy',
    'cultist hunter',
    'gunner',
    'town hunter',
    'doppelganger',
    'cupid',
    'blacksmith',
    'prince',
    'tanner',
    'wild child',
    'drunk',
    'apprentice seer',
    'seer',
    'traitor',
]

WEREWOLF_BOTS = [
    175844556,  # @werewolfbot
]

WEREWOLF_CHAT_ID = -1001077911861


class WerewolfSafeList(Plugin):
    def __init__(self):
        super(WerewolfSafeList, self).__init__('safelist')
        self.lock = threading.Lock()
        self.config = None
        self.safelist = []
        self.message_id = None
        self.safe_roles = []
        self.moderators = []
        self.last_message_hash = ''
        self.last_update = None

    def get_default_config(self):
        return {
            'short_name': self.name,
            'enabled': True,
            'werewolf_bots': WEREWOLF_BOTS,
            'werewolf_safe_roles': WEREWOLF_SAFE_ROLES,
            'werewolf_chat_id': WEREWOLF_CHAT_ID,
            'max_forward_date_diff': 120
        }

    def configure(self, config):
        self.config = config
        self.safe_roles = config.get('werewolf_safe_roles')
        self.bots = config.get('werewolf_bots')
        self.chat_id = config.get('werewolf_chat_id')

    def setup_handlers(self, adapter):
        self.add_handler(MessageHandler([
            CommonFilters.forwarded,
            lambda msg: msg.forward_from.id in self.bots,
            lambda msg: any(x in trim_accents(msg.text.lower()) for x in self.safe_roles)
        ],
            self.on_text,
            strict=True))
        self.add_handler(CommandHandler('sf', self.on_sf_command, command_description='Safelist')
                         .add_argument('--clear', help='Clear the safe list', action='store_true')
                         .add_argument('--roles', help='List all the safe roles', action='store_true')
                         .add_argument('--add-role', help='Temporarily adds a safe role')
                         .add_argument('--remove-role', help='Temporarily removes a safe role'))
        self.add_handler(CommandHandler('sl', self.on_sf_command, command_description='Safelist')
                         .add_argument('--clear', help='Clear the safe list', action='store_true')
                         .add_argument('--roles', help='List all the safe roles', action='store_true')
                         .add_argument('--add-role', help='Temporarily adds a safe role')
                         .add_argument('--remove-role', help='Temporarily removes a safe role'))
        self.add_handler(CommandHandler('sfclear', self.on_sfclear_command, command_description='Clear safelist'))
        self.add_handler(CommandHandler('slclear', self.on_sfclear_command, command_description='Clear safelist'))

    def setup_schedules(self, adapter):
        pass

    def clear_safelist(self, update, notify=False):
        with self.lock:
            if len(self.safelist) == 0 and notify:
                update.message.reply_text('❌ Safelist is already cleared.')
                return
            self.message_id = None
            self.safelist.clear()
            log.info('Safelist cleared')
            if notify:
                self.adapter.bot.sendMessage(chat_id=self.chat_id, text="🚮 {} cleared the safelist.".format(update.message.from_user.first_name))
            else:
                self.adapter.bot.sendMessage(chat_id=self.chat_id, text="🚮 Safelist cleared.")
            # update.message.reply_text('🚮 Cleared safelist.')

    def on_sfclear_command(self, update, *args, **kwargs):
        self.clear_safelist(update, True)

    def on_sf_command(self, update, *args, **kwargs):
        clear = kwargs.get('clear')
        roles = kwargs.get('roles')
        add_role = kwargs.get('add_role')
        remove_role = kwargs.get('remove_role')

        if clear:
            self.clear_safelist(update, True)
        elif roles:
            self.show_safe_roles(update)
        else:
            if add_role:
                self.add_role(update, add_role)
            if remove_role:
                self.remove_role(update, remove_role)
            if not add_role and not remove_role:
                self.show_safelist(True)

    def add_role(self, update, role):
        if role in self.safe_roles:
            update.message.reply_text('❌ Safe role found.')
        else:
            self.safe_roles.append(role)
            update.message.reply_text('✅ Role added.')

    def remove_role(self, update, role):
        if role in self.safe_roles:
            self.safe_roles.remove(role)
            update.message.reply_text('🚮 Safe role removed.')
        else:
            update.message.reply_text('❌ Safe role not found.')

    def show_bots(self, update):
        update.message.reply_text("*Bots:*\n\n{}".format(self.generate_bots_response()), parse_mode='Markdown')

    def show_safe_roles(self, update):
        update.message.reply_text("*Roles:*\n\n{}".format(self.generate_roles_response()), parse_mode='Markdown')

    def generate_roles_response(self):
        with self.lock:
            roles = self.safe_roles
            response = "\n".join(roles)
            return response

    def generate_bots_response(self):
        with self.lock:
            bots = self.bots
            response = "\n".join(bots)
            return response

    def generate_safelist_response(self):
        roles = {}
        responses = []
        with self.lock:
            for slmember in self.safelist:
                role = slmember.get_role()
                if role in roles:
                    roles[role] += 1
                else:
                    roles[role] = 1

            for role, count in roles.items():
                response = "{}: {}".format(role.capitalize(), count)
                responses.append(response)

        return "\n".join(responses) if len(responses) > 0 else "Empty."

    def show_safelist(self, force_new=False):
        text = "*Safelist*:\n\n{}".format(self.generate_safelist_response())
        texthash = hashlib.sha256(text.encode())
        if not force_new and texthash == self.last_message_hash:
            return
        self.last_message_hash = texthash
        message = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if not force_new and self.message_id:
            message['message_id'] = self.message_id
            self.adapter.bot.editMessageText(**message)
        else:
            msg = self.adapter.bot.sendMessage(**message)
            self.message_id = msg.message_id

    def add_safelist_member(self, update, member):
        self.safelist.append(member)
        log.info("Added {} to safelist".format(member.get_role()))
        update.message.reply_text('✅ Added to safelist.')

    def on_text(self, update):
        dt = update.message.date - update.message.forward_date
        text = trim_accents(update.message.text.lower())
        # if dt.total_seconds() > self.config.get('max_forward_date_diff'):
        #     log.info("Player forwarded an old message")
        #     update.message.reply_text('❌ Your forward is too old.')
        #     return

        if "players alive" in text:
            return

        dtu = update.message.forward_date - self.last_update if self.last_update is not None else None
        if dtu is not None and dtu.total_seconds() > self.config.get('max_forward_date_diff') and len(self.safelist) > 0:
            self.clear_safelist(update, False)

        added = False
        with self.lock:
            if any(member.get_user().id == update.message.from_user.id for member in self.safelist):
                update.message.reply_text('❌ You are already in the safelist.')
                return

            for role in self.safe_roles:
                if role in text and 'sorcerer' not in text:
                    # Fix Sorcerer containing seer
                    member = SafelistMember(update.message.from_user, role)
                    self.add_safelist_member(update, member)
                    added = True
                    self.last_update = update.message.forward_date
                    break
        if added:
            self.show_safelist()
