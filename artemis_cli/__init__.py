import click
import cmd
import diana
import diana.packet as packets
import diana.tracking
import re
import sys
import threading


def validate(func):
    def wrapper(line=None):
        try:
            params = func.__click_params__
            params.reverse()
        except AttributeError:
            params = []

        command = click.Command(name='connect', callback=func,
                                params=params, add_help_option=False)
        args = line.split(' ') if line else []

        try:
            return command.main(
                args, prog_name='disconnected',
                standalone_mode=False,
            )
        except click.UsageError as e:
            print(e.format_message())
    return wrapper


class ClickCmd(cmd.Cmd):
    def __getattribute__(self, item):
        member = super().__getattribute__(item)
        if item == 'do_help' or not item.startswith('do_'):
            return member

        return validate(member)


class Disconnected(ClickCmd):
    prompt = 'disconnected: '
    connection = None

    def do_version(self):
        """
        print the artemis-cli version
        """
        print("artemis-cli, v0.0.0")

    def do_quit(self):
        exit(0)

    do_exit = do_quit

    @click.argument('host')
    def do_connect(self, host):
        """
        connect [host]
        Connect to the given host
        """
        print("connecting to %s ..." % host)
        try:
            self.connection = diana.connect(host)
            return True
        except Exception as e:
            print("failed to connect: %s" % e)


class Connected(ClickCmd):
    prompt = 'artemis > '

    def __init__(self, tx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tx = tx

    def do_ready(self):
        self._tx(packets.ReadyPacket())


class BaseProcessor:
    first_re = re.compile(r'(.)([A-Z][a-z]+)')
    second_re = re.compile(r'([a-z0-9])([A-Z])')

    def _snake_case(self, name):
        s1 = re.sub(self.first_re, r'\1_\2', name)
        return re.sub(self.second_re, r'\1_\2', s1).lower()

    def process(self, packet):
        name = type(packet).__name__
        name = self._snake_case(name.replace('Packet', ''))
        func = getattr(self, name, None)
        if not func:
            print("--- unhandled packet: %s ---" % type(packet).__name__)
            return
        return func(packet)


class GameState:
    def __init__(self):
        self.ships = None
        self.consoles = None
        self._ship_index = None

        self._tracker = diana.tracking.Tracker()

    def rx(self, packet):
        self._tracker.rx(packet)

    @property
    def ship(self):
        if self.ships:
            return self.ships[self._ship_index]

    @ship.setter
    def ship(self, ship_index):
        self._ship_index = ship_index


class GameProcessor(BaseProcessor):
    @classmethod
    def run(cls, rx):
        processor = GameProcessor()

        for packet in rx:
            processor.process(packet)

    def __init__(self):
        self._state = GameState()

    def process(self, packet):
        self._state.rx(packet)
        return super().process(packet)

    def all_ship_settings(self, packet: packets.AllShipSettingsPacket):
        self._state.all_ships = packet.ships

    def console_status(self, status: packets.ConsoleStatusPacket):
        self._state.consoles = status.consoles
        self._state.ship = status.ship

    def heartbeat(self, packet: packets.HeartbeatPacket):
        pass

    def comms_incoming(self, packet: packets.CommsIncomingPacket):
        print("incoming message from %s: %s"
              % (packet.sender, packet.message))

    def noise(self, noice: packets.NoisePacket):
        pass

    def object_update(self, packet: packets.ObjectUpdatePacket):
        pass

    def version(self, version):
        print("server v%s.%s.%s" % (version.major, version.minor, version.patch))
        if version.major == 2 and version.minor < 1:
            packets.Console = packets.Console_pre_2_1
        elif version.major == 2 and version.minor in (1, 2):
            packets.Console = packets.Console_2_1
        else:
            packets.Console = packets.Console_2_3

    def welcome(self, welcome):
        print(welcome.message)


def cli():
    loop = Disconnected()
    if len(sys.argv) > 1:
        loop.onecmd(' '.join(sys.argv[1:]))
    else:
        loop.cmdloop()

    tx, rx = loop.connection

    recv_thread = threading.Thread(
        name='RX thread',
        target=GameProcessor.run, args=(rx,),
        daemon=True,
    )
    recv_thread.start()

    connected_loop = Connected(tx)
    connected_loop.cmdloop()
