import binascii
import hashlib
import os
from typing import Tuple

from discord import Message

MAX_MESSAGE_LENGTH = 2000


def hash_password(password: str) -> Tuple[str, str]:
    salt = os.urandom(8)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return (
        binascii.hexlify(key).decode('utf-8'),
        binascii.hexlify(salt).decode('utf-8')
    )


def verify_password(password: str, hashed_password: Tuple[str, str]) -> bool:
    actual_key = binascii.unhexlify(hashed_password[0].encode('utf-8'))
    salt = binascii.unhexlify(hashed_password[1].encode('utf-8'))
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return key == actual_key


async def reply(original_message: Message, text: str) -> None:
    lines = text.split('\n')
    messages = ['']
    for line in lines:
        if len(messages[-1] + line) > MAX_MESSAGE_LENGTH:
            messages.append('')
        messages[-1] += line + '\n'
    for message in messages:
        await original_message.channel.send(message.strip())
