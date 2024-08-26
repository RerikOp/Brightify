import abc
import enum
from dataclasses import dataclass, field
from types import TracebackType
from typing import Optional, Tuple, Type, Dict, List, Union, Literal
import re


class VCPError(Exception):
    """Base class for all VCP related errors."""
    pass


class VCPIOError(VCPError):
    """Raised on VCP IO errors."""
    pass


class VCPPermissionError(VCPError):
    """Raised on VCP permission errors."""
    pass


class InputSourceValueError(VCPError):
    """
    Raised upon an invalid (out of spec) input source value.

    https://github.com/newAM/monitorcontrol/issues/93

    Attributes:
        value (int): The value of the input source that was invalid.
    """

    def __init__(self, message: str, value: int):
        super().__init__(message)
        self.value = value


class VCP(abc.ABC):
    def __init__(self, name: Optional[str] = None):
        self.name = name

    @abc.abstractmethod
    def __enter__(self):
        pass

    @abc.abstractmethod
    def __exit__(
            self,
            exception_type: Optional[Type[BaseException]],
            exception_value: Optional[BaseException],
            exception_traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        pass

    @abc.abstractmethod
    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.

        :param code: Feature code.
        :param value: Feature value.
        :raises VCPError: Failed to set VCP feature.
        """
        pass

    @abc.abstractmethod
    def get_vcp_feature(self, code: int) -> Tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.

        :param code: Feature code.
        :returns: Current feature value, maximum feature value.
        :raises VCPError: Failed to get VCP feature.
        """
        pass

    @abc.abstractmethod
    def get_vcp_capabilities(self) -> str:
        """
        Gets capabilities string from the virtual control panel.
        :return: Capabilities string.
        :raises VCPError: Failed to get VCP feature.
        """
        pass


@dataclass(frozen=True)
class VCPCode:
    value: int
    type: Literal["ro", "rw", "wo"]
    function: Literal["nc", "c"]

    @property
    def readable(self) -> bool:
        """Returns true if the code can be read."""
        if self.type == "wo":
            return False
        else:
            return True

    @property
    def writeable(self) -> bool:
        """Returns true if the code can be written."""
        if self.type == "ro":
            return False
        else:
            return True


class VCPCodeDefinition:
    restore_factory_default_image: VCPCode = VCPCode(value=0x04, type="wo", function="nc")
    image_luminance: VCPCode = VCPCode(value=0x10, type="rw", function="c")
    image_contrast: VCPCode = VCPCode(value=0x12, type="rw", function="c")
    image_color_preset: VCPCode = VCPCode(value=0x14, type="rw", function="nc")
    active_control: VCPCode = VCPCode(value=0x52, type="ro", function="nc")
    input_select: VCPCode = VCPCode(value=0x60, type="rw", function="nc")
    image_orientation: VCPCode = VCPCode(value=0xAA, type="ro", function="nc")
    display_power_mode: VCPCode = VCPCode(value=0xD6, type="rw", function="nc")


@enum.unique
class ColorPreset(enum.Enum):
    """Monitor color presets."""
    COLOR_TEMP_4000K = 0x03
    COLOR_TEMP_5000K = 0x04
    COLOR_TEMP_6500K = 0x05
    COLOR_TEMP_7500K = 0x06
    COLOR_TEMP_8200K = 0x07
    COLOR_TEMP_9300K = 0x08
    COLOR_TEMP_10000K = 0x09
    COLOR_TEMP_11500K = 0x0A
    COLOR_TEMP_USER1 = 0x0B
    COLOR_TEMP_USER2 = 0x0C
    COLOR_TEMP_USER3 = 0x0D


@enum.unique
class PowerMode(enum.Enum):
    """Monitor power modes."""
    #: On.
    on = 0x01
    #: Standby.
    standby = 0x02
    #: Suspend.
    suspend = 0x03
    #: Software power off.
    off_soft = 0x04
    #: Hardware power off.
    off_hard = 0x05


@enum.unique
class InputSource(enum.Enum):
    """Monitor input sources."""
    OFF = 0x00
    ANALOG1 = 0x01
    ANALOG2 = 0x02
    DVI1 = 0x03
    DVI2 = 0x04
    COMPOSITE1 = 0x05
    COMPOSITE2 = 0x06
    SVIDEO1 = 0x07
    SVIDEO2 = 0x08
    TUNER1 = 0x09
    TUNER2 = 0x0A
    TUNER3 = 0x0B
    CMPONENT1 = 0x0C
    CMPONENT2 = 0x0D
    CMPONENT3 = 0x0E
    DP1 = 0x0F
    DP2 = 0x10
    HDMI1 = 0x11
    HDMI2 = 0x12


@dataclass
class Capabilities:
    prot: str = ""
    type: str = ""
    model: str = ""
    cmds: Dict[int, Dict] = field(default_factory=dict)
    vcp: Dict[int, Dict] = field(default_factory=dict)
    mswhql: str = ""
    asset_eep: str = ""
    mccs_ver: str = ""
    window: str = ""
    vcpname: str = ""
    inputs: List[Union[int, str]] = field(default_factory=list)
    color_presets: List[Union[int, str]] = field(default_factory=list)


def parse_capabilities(caps_str: str) -> Capabilities:
    """
    Converts the capabilities string into a nice dict
    """
    parsed_values = {}

    for key in Capabilities.__annotations__:
        if key in ["cmds", "vcp"]:
            parsed_values[key] = _cap_to_dict(_extract_cap(caps_str, key))
        else:
            parsed_values[key] = _extract_cap(caps_str, key)

    # Parse the input sources into a text list for readability
    input_source_cap = VCPCodeDefinition.input_select.value
    if input_source_cap in parsed_values["vcp"]:
        inputs = []
        input_val_list = list(parsed_values["vcp"][input_source_cap].keys())
        input_val_list.sort()
        for val in input_val_list:
            try:
                input_source = InputSource(val)
            except ValueError:
                input_source = val
            inputs.append(input_source)
        parsed_values["inputs"] = inputs

    # Parse the color presets into a text list for readability
    color_preset_cap = VCPCodeDefinition.image_color_preset.value
    if color_preset_cap in parsed_values["vcp"]:
        color_presets = []
        color_val_list = list(parsed_values["vcp"][color_preset_cap].keys())
        color_val_list.sort()
        for val in color_val_list:
            try:
                color_source = ColorPreset(val)
            except ValueError:
                color_source = val
            color_presets.append(color_source)
        parsed_values["color_presets"] = color_presets

    return Capabilities(**parsed_values)


# Helper functions


def _extract_cap(caps_str: str, key: str) -> str:
    """
    Extracts a capability from the capabilities string.
    :param caps_str: Capabilities string.
    :param key: Capability key.
    :return: Capability value.
    """
    pattern = re.compile(rf"{re.escape(key)}\((.*?)\)", re.IGNORECASE)
    match = pattern.search(caps_str)

    if match:
        return match.group(1)
    return ""


def _cap_to_dict(caps_str: str) -> dict:
    """
    Parses the VCP capabilities string to a dictionary.
    Non-continuous capabilities will include an array of all supported values.
    :return: Dict with all capabilities in hex.
    example: Expected string "04 14(05 06) 16" is converted to:
              {0x04: {}, 0x14: {0x05: {}, 0x06: {}}, 0x16: {}}
    """
    if not caps_str:
        return {}

    result_dict = {}
    group = []
    prev_val = None

    for chunk in caps_str.replace("(", " ( ").replace(")", " ) ").split():
        if chunk == "(":
            group.append(prev_val)
        elif chunk == ")":
            group.pop()
        else:
            val = int(chunk, 16)
            if not group:
                result_dict[val] = {}
            else:
                d = result_dict
                for g in group:
                    d = d[g]
                d[val] = {}
            prev_val = val

    return result_dict
