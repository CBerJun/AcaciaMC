"""
music - Generate redstone music from MIDI file
NOTE Python package `mido` is required.
"""

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.generator import MCFunctionFile
from acaciamc.ast import ModuleMeta
from acaciamc.error import ErrorType

class MusicType(Type):
    """
    Music(
        path: str,
        looping: bool = False,
        loop_interval: int = 50,
        execute_condition: str = "as @a at @s",
        note_offset: int = 0,
        chunk_size: int = 500,
        speed: int = 100
    )

    A music to generate from MIDI file `path`.
    If `looping` is True, the music will be played repeatingly, with
    interval `loop_interval` before replaying.
    `execute_condition` sets the subcommand of /execute used by
    /playsound. By setting this you can specify where the music is
    played and who would hear it.
    `note_offset` would make the whole music higher if it is positive,
    or lower if negative.
    Since music runs a LOT of commands every tick, we seperate commands
    into several files to make sure you are not running too many commands
    every tick. `chunk_size` determines how many commands there will be
    in 1 file.
    `speed` affects the speed of music in percentage.
    """
    name = "Music"

    def do_init(self):
        def _new(func: BinaryFunction):
            arg_path = func.arg_require("path", BuiltinStringType)
            arg_loop = func.arg_optional(
                "looping",
                BoolLiteral(False, func.compiler), BuiltinBoolType
            )
            arg_loop_intv = func.arg_optional(
                "loop_interval", IntLiteral(50, func.compiler), BuiltinIntType
            )
            if not isinstance(arg_loop, BoolLiteral):
                func.arg_error("looping", "must be a constant")
            if not isinstance(arg_loop_intv, IntLiteral):
                func.arg_error("loop_interval", "must be a constant")
            arg_exec = func.arg_optional(
                "execute_condition",
                String("as @a at @s", func.compiler),
                BuiltinStringType
            )
            arg_note = func.arg_optional(
                "note_offset", IntLiteral(0, func.compiler), BuiltinIntType)
            arg_chunk = func.arg_optional(
                "chunk_size", IntLiteral(500, func.compiler), BuiltinIntType)
            arg_speed = func.arg_optional(
                "speed", IntLiteral(100, func.compiler), BuiltinIntType)
            if not isinstance(arg_note, IntLiteral):
                func.arg_error("note_offset", "must be a constant")
            if not isinstance(arg_chunk, IntLiteral):
                func.arg_error("chunk_size", "must be a constant")
            if not isinstance(arg_speed, IntLiteral):
                func.arg_error("speed", "must be a constant")
            if arg_chunk.value < 1:
                func.arg_error("chunk_size", "must be positive")
            if arg_speed.value < 1:
                func.arg_error("speed", "must be positive")
            func.assert_no_arg()
            try:
                midi = mido.MidiFile(arg_path.value)
            except Exception as err:
                func.compiler.error(ErrorType.IO,
                                    message="MIDI parser: %s" % err)
            exec_condition = arg_exec.value
            note_offset = arg_note.value
            looping = arg_loop_intv.value if arg_loop.value else -1
            chunk_size = arg_chunk.value
            speed = arg_speed.value / 100
            return Music(
                midi, exec_condition, looping, note_offset,
                chunk_size, speed, func.compiler
            )

        self.attribute_table.set("__new__",
            BinaryFunction(_new, self.compiler))

class Music(AcaciaExpr):
    # NOTE We are using `MT` to refer to 1 MIDI tick and `GT` for 1 MC game
    # tick.
    # CONFIGS
    DEFAULT_VOLUME = 100 # 0~127
    DEFAULT_INSTRUMENT = "note.harp" # Piano
    ID2INSTRUMENT = {
        0: "note.harp"
    }

    def __init__(self, midi, exec_condition: str, looping: int,
                 note_offset: int, chunk_size: int, speed: float, compiler):
        super().__init__(compiler.types[MusicType], compiler)
        self.midi = midi
        self.execute_condition = exec_condition
        self.note_offset = note_offset
        self.chunk_size = chunk_size
        self.tracks = [t.copy() for t in midi.tracks]
        # Check MIDI type
        if midi.type != 0 and midi.type != 1:
            self.compiler.error(ErrorType.ANY,
                message="Unsupported MIDI type: %d" % midi.type)
        # Speed settings
        self.bpm = 120
        self.mt_per_beat = midi.ticks_per_beat
        self.user_speed = speed
        # Ticking
        self.mt = 0
        self.gt = 0.0
        self.gt_int = 0 # Always == round(self.gt)
        self.last_gt_int = 0
        # last_msg_mt: track id to MT when last Message is handled
        self.last_msg_mt = dict.fromkeys(range(len(midi.tracks)), 0)
        # Channel info
        self.channel_volume = {} # channel id to volume (0-127)
        self.channel_instrument = {} # channel id to instrument id
        # Timer:
        #   when 0 <= timer <= music length, the music is playing
        #   when timer > music length, the music has ended
        #   when timer < 0, it's the countdown of starting playing
        self.timer = self.compiler.types[BuiltinIntType].new_var()
        # Create file
        self.files = []
        # file_sep_mt: in which GT we seperate the file
        self.file_sep_gt = []
        self.cur_chunk_size = 0 # Commands written in current file
        self.new_file() # Initial file
        # Go
        while not self.is_finished():
            self.main_loop()
        GT_LEN = self.gt_int # Length of music in GT
        # The last file may be useless
        if not self.files[-1].has_content():
            self.files.pop()
            self.file_sep_gt.pop()
        # Add file
        for file in self.files:
            self.compiler.add_file(file)
        self.file_sep_gt.append(GT_LEN + 1)
        # Create GT loop using `schedule` module
        def _gt_loop(func: BinaryFunction):
            func.assert_no_arg()
            cmds = []
            cmds.extend(
                export_execute_subcommands(
                    ["if score %s matches %d..%d" % (
                        self.timer,
                        self.file_sep_gt[i], self.file_sep_gt[i+1] - 1
                    )], main=file.call()
                )
                for i, file in enumerate(self.files)
            )
            cmds.extend(
                export_execute_subcommands(
                    ["if score %s matches ..%d" % (self.timer, GT_LEN)],
                    main=cmd
                )
                for cmd in self.timer.iadd(IntLiteral(1, self.compiler))
            )
            if looping >= 0:
                cmds.extend(export_execute_subcommands(
                    ["if score %s matches %d" % (self.timer, GT_LEN + 1)],
                    main=cmd
                ) for cmd in IntLiteral(-looping, func.compiler)
                             .export(self.timer))
            return result_none(cmds, func.compiler)
        # Register this to be called every tick
        register_loop.call((BinaryFunction(_gt_loop, self.compiler),), {})
        # Create attributes
        self.attribute_table.set("_timer", self.timer)
        self.attribute_table.set("LENGTH", IntLiteral(GT_LEN, self.compiler))
        def _play(func: BinaryFunction):
            """
            .play(timer: int = 0)

            Start playing the music. When `timer` < 0, its the delay
            of playing. When `timer` >= 0, its where the music starts
            playing.
            """
            arg_timer = func.arg_optional("timer",
                IntLiteral(0, func.compiler), BuiltinIntType)
            func.assert_no_arg()
            cmds = arg_timer.export(self.timer)
            return result_none(cmds, func.compiler)
        self.attribute_table.set("play", BinaryFunction(_play, self.compiler))
        def _stop(func: BinaryFunction):
            """.stop(): Stop the music"""
            func.assert_no_arg()
            cmds = IntLiteral(GT_LEN + 2, func.compiler).export(self.timer)
            return result_none(cmds, func.compiler)
        self.attribute_table.set("stop", BinaryFunction(_stop, self.compiler))

    def main_loop(self):
        # Read messages
        for i, track in enumerate(self.tracks):
            if not track:
                continue
            message = track[0]
            if message.time > self.mt - self.last_msg_mt[i]:
                continue
            # Handle message
            mtype = message.type
            if mtype == "note_on":
                if message.velocity != 0:
                    self.play_note(message)
            elif mtype == "set_tempo":
                self.bpm = 6E+7 / message.tempo
            elif message.is_cc():
                if message.control == 7: # Volume
                    self.channel_volume[message.channel] = message.value
            elif mtype == "program_change":
                self.channel_instrument[message.channel] = message.program
            # Reset timer
            self.last_msg_mt[i] = self.mt
            track.pop(0)
        # Time increment
        self.mt += 1
        # bpm * mt_per_beat is MT per minute. Divide it by 1200 to get mt
        # per MT, and multiply it by `user_speed` at last
        self.gt += 1 / (self.bpm * self.mt_per_beat * self.user_speed / 1200)
        self.gt_int = round(self.gt)
        # Update last_gt_int
        if self.gt_int > self.last_gt_int:
            self.last_gt_int = self.gt_int
            # New file check
            if self.cur_chunk_size >= self.chunk_size:
                self.new_file()

    def new_file(self):
        self.cur_file = MCFunctionFile()
        self.files.append(self.cur_file)
        self.cur_file.write_debug("# Music loop")
        self.file_sep_gt.append(self.gt_int)
        self.cur_chunk_size = 0

    def is_finished(self):
        return not any(self.tracks)
    
    def get_instrument(self, channel: int) -> str:
        """Get MC sound of channel."""
        ins_id = self.channel_instrument.get(channel)
        return self.ID2INSTRUMENT.get(ins_id, self.DEFAULT_INSTRUMENT)

    def get_volume(self, channel: int, velocity: int) -> float:
        """Get MC volume (0~1) according to channel and velocity."""
        channel_v = self.channel_volume.get(channel, self.DEFAULT_VOLUME)
        return velocity * channel_v / 127 / 127

    def get_pitch(self, note: int) -> float:
        """Get MC pitch from MIDI note"""
        return 2 ** ((note + self.note_offset - 54) / 12 - 1)

    def play_note(self, message):
        """Play a note according to note_on Message"""
        volume = self.get_volume(message.channel, message.velocity)
        pitch = self.get_pitch(message.note)
        sound = self.get_instrument(message.channel)
        gt = self.gt_int
        self.cur_file.write(
            "execute if score %s matches %d %s run " %
            (self.timer, gt, self.execute_condition) + 
            "playsound %s @s ~~~ %.2f %.3f" %
            (sound, volume, pitch)
        )
        self.cur_chunk_size += 1

def acacia_build(compiler):
    global mido, register_loop
    try:
        import mido
    except ImportError:
        compiler.error(ErrorType.ANY,
                       message="Python module 'mido' is required")
    schedule = compiler.get_module(ModuleMeta("schedule"))
    register_loop = schedule.attribute_table.lookup("register_loop")
    compiler.add_type(MusicType)
    return {
        "Music": compiler.types[MusicType]
    }

