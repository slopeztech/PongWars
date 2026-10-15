"""@package pongwars.net.codec
@brief Message serialisation, swappable behind the Codec interface.
"""

import json
import zlib
from abc import ABC, abstractmethod

from pongwars.net.protocol import Message, ProtocolError, from_dict, to_dict

MAX_PACKET = 60000


class Codec(ABC):
    """@brief Converts messages to bytes and back."""

    @abstractmethod
    def encode(self, message: Message) -> bytes:
        """@brief Serialise a message.
        @param message Message to send.
        @return Wire bytes.
        """

    @abstractmethod
    def decode(self, data: bytes) -> Message:
        """@brief Parse wire bytes.
        @param data Received bytes.
        @return The message.
        @throws ProtocolError If the data is malformed or too large.
        """


class JsonCodec(Codec):
    """@brief Compressed JSON; never trusts the input size or shape."""

    def encode(self, message: Message) -> bytes:
        """@brief Serialise a message.
        @param message Message to send.
        @return zlib-compressed JSON.
        @throws ProtocolError If the packet would be too large.
        """
        raw = zlib.compress(json.dumps(to_dict(message), separators=(",", ":")).encode())
        if len(raw) > MAX_PACKET:
            raise ProtocolError("packet too large")
        return raw

    def decode(self, data: bytes) -> Message:
        """@brief Parse wire bytes.
        @param data Received bytes.
        @return The message.
        @throws ProtocolError If the data is malformed or too large.
        """
        if len(data) > MAX_PACKET:
            raise ProtocolError("packet too large")
        try:
            inflater = zlib.decompressobj()
            text = inflater.decompress(data, MAX_PACKET * 4)
            if inflater.unconsumed_tail:
                raise ProtocolError("packet too large")
            return from_dict(json.loads(text))
        except ProtocolError:
            raise
        except (zlib.error, ValueError, TypeError, RecursionError) as exc:
            raise ProtocolError("malformed packet") from exc
