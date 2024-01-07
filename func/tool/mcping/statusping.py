import json
import socket
import struct
import time


class StatusPing:
    def __init__(self, host: str = "localhost", port: int = 25565, timeout: int = 5):
        self._host = host
        self._port = port
        self._timeout = timeout

    @staticmethod
    def _unpack_varint(sock: socket.socket) -> int:
        data = 0
        for i in range(5):
            ordinal = sock.recv(1)
            if len(ordinal) == 0:
                break

            byte = ord(ordinal)
            data |= (byte & 0x7F) << 7 * i

            if not byte & 0x80:
                break

        return data

    @staticmethod
    def _pack_varint(data: int) -> bytes:
        ordinal = b""

        while True:
            byte = data & 0x7F
            data >>= 7
            ordinal += struct.pack("B", byte | (0x80 if data > 0 else 0))

            if data == 0:
                break

        return ordinal

    def _pack_data(self, data: str | int | float | bytes) -> bytes:  # noqa: PYI041
        if isinstance(data, str):
            data = data.encode("utf8")
            return self._pack_varint(len(data)) + data
        if isinstance(data, int):
            return struct.pack("H", data)
        if isinstance(data, float):
            return struct.pack("Q", int(data))
        return data

    def _send_data(self, connection: socket.socket, *args: str | int | float | bytes) -> None:  # noqa: PYI041
        data = b""

        for arg in args:
            data += self._pack_data(arg)

        connection.send(self._pack_varint(len(data)) + data)

    def _read_fully(self, connection: socket.socket, *, extra_varint: bool = False) -> bytes:
        packet_length = self._unpack_varint(connection)
        packet_id = self._unpack_varint(connection)
        byte = b""

        if extra_varint:
            if packet_id > packet_length:
                self._unpack_varint(connection)

            extra_length = self._unpack_varint(connection)

            while len(byte) < extra_length:
                byte += connection.recv(extra_length)

        else:
            byte = connection.recv(packet_length)

        return byte

    def get_status(self) -> dict:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(self._timeout)
            connection.connect((self._host, self._port))
            self._send_data(connection, b"\x00\x00", self._host, self._port, b"\x01")
            self._send_data(connection, b"\x00")

            data = self._read_fully(connection, extra_varint=True)

            self._send_data(connection, b"\x01", time.time() * 1000)
            unix = self._read_fully(connection)

        response: dict = json.loads(data.decode("utf8"))
        response["ping"] = int(time.time() * 1000) - struct.unpack("Q", unix)[0]

        return response

