import ctypes
from ctypes import wintypes
from threading import Thread
from copy import deepcopy
from time import sleep, time
from math import radians as math_radians, cos as math_cos, sin as math_sin, atan2 as math_atan2, sqrt as math_sqrt, degrees as math_degrees
import tkinter as tk
from PIL import Image, ImageTk
from json import dump as json_dump, load as json_load
from os import rename as os_rename, path as os_path, remove as os_remove, listdir as os_listdir

import button_map


user32 = ctypes.WinDLL('user32')
xinput1_4 = ctypes.WinDLL('XInput1_4.dll')


mouse_move_time = time()

mouse_pos = (0, 0)
left_stick_pos = (0, 0)
right_stick_pos = (0, 0)

pressed_keys = ()

mouse_speed_indicator = None

pressed_movement_keys = {"azeron":(),"mouse":()}

used_inputs = {
    "movement_keys":{
        "azeron":{},
        "mouse":{}
    },
    "sticks":{
        "left":False,
        "right":False
    },
    "inputs":{},
    "xinputs":{},
}


profile = {}
settings = {}


empty_profile_template = {"azeron_keys": {"1": [], "2": [], "3": [], "4": [], "5": [], "6": [], "7": [], "8": [], "9": [], "10": [], "11": [], "12": [], "14": [], "15": [], "16": [], "17": [], "19": [], "20": [], "22": [], "23": [], "28": [], "29": [], "30": [], "31": [], "13": [], "18": [], "36": [], "37": [], "38": [], "41": []}, "stick": "xinput-l", "mouse_stick": "xinput-l", "mouse_keys": {"right": [2], "left": [1], "middle": [4], "forward": [6], "back": [5], "dpi": [], "1": [5], "2": [6], "3": [2], "4": [1], "5": [4], "6": [], "7": [], "8": [], "9": [], "10": [], "11": [], "12": [], "14": [], "15": [], "16": [], "17": [], "20": [], "22": [], "28": [], "29": [], "30": [], "31": [], "g7": [], "g8": [], "g9": [], "sl": [], "sr": []}}


class XINPUT_GAMEPAD(ctypes.Structure):
    # Represents the state of an Xbox controller's gamepad buttons and sticks
    _fields_ = [
        ("wButtons", wintypes.WORD),  # Button state 
        ("bLeftTrigger", ctypes.c_ubyte),  # Analog value of the left trigger
        ("bRightTrigger", ctypes.c_ubyte),  # Analog value of the right trigger
        ("sThumbLX", ctypes.c_short),  # Left thumbstick X-axis position
        ("sThumbLY", ctypes.c_short),  # Left thumbstick Y-axis position
        ("sThumbRX", ctypes.c_short),  # Right thumbstick X-axis position
        ("sThumbRY", ctypes.c_short)  # Right thumbstick Y-axis position
    ]

class XINPUT_STATE(ctypes.Structure):
    # Represents the state of an Xbox controller, including packet number and gamepad data
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),  # Packet number for controller state (increments with each update)
        ("Gamepad", XINPUT_GAMEPAD)  # Nested structure representing the gamepad's button and stick states
    ]
    
class POINT(ctypes.Structure):
    # Represents a point (x, y) in a 2D coordinate system
    _fields_ = [("x", ctypes.c_long),  # X-coordinate
                ("y", ctypes.c_long)]  # Y-coordinate

class MSLLHOOKSTRUCT(ctypes.Structure):
    # Represents the information passed to a low-level mouse hook (used for mouse input monitoring)
    _fields_ = [
        ("pt", wintypes.POINT),  # The point where the mouse event occurred (contains x, y coordinates)
        ("mouseData", wintypes.DWORD),  # Additional mouse data (e.g., scroll wheel information)
        ("flags", wintypes.DWORD),  # Event-internal flags
        ("time", wintypes.DWORD),  # Timestamp of the mouse event
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))  # Pointer to extra information 
    ]


def get_xinput_state(controller_index:int=0):
    # Retrieves the state of the Xbox controller at the given index (default is 0)
    # It uses the XInput API to get the current controller state
    state = XINPUT_STATE()
    # XInputGetState returns 0 if successful. If not, return None (controller not connected)
    if xinput1_4.XInputGetState(controller_index, ctypes.byref(state)) != 0:
        return None
    return state  # Return the state of the controller

def get_key_from_value(dictionary:dict, value:str):
    # Finds the first key in the dictionary that corresponds to the given value
    # If no such key is found, it returns the value itself
    for key, val in dictionary.items():
        if val == value:
            return key
    return value  # Return the value itself if not found in the dictionary

def low_level_mouse_proc(nCode, wParam, lParam):
    # Callback function for handling low-level mouse events (e.g., scroll events)
    if wParam == 0x020A:  # Mouse scroll event (WM_MOUSEWHEEL)
        # Extracts scroll data from the mouse event (high word of mouseData contains scroll amount)
        scroll_amount = ctypes.c_short(ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents.mouseData >> 16).value
        if scroll_amount > 0:
            # Show "mouse_scroll_up" image and hide "mouse_scroll_down"
            app.set_image_visibility(f"mouse_scroll_down", False)
            app.set_image_visibility(f"mouse_scroll_up", True)
        else:
            # Show "mouse_scroll_down" image and hide "mouse_scroll_up"
            app.set_image_visibility(f"mouse_scroll_up", False)
            app.set_image_visibility(f"mouse_scroll_down", True)
    # Horizontal scrolling (0x020E) or other mouse events can be added here
    return user32.CallNextHookEx(None, nCode, wParam, ctypes.c_void_p(lParam))  # Pass the event to the next hook in the chain

def scroll_wheel_listener():
    # Sets up a low-level hook to listen for mouse scroll events (both vertical and horizontal).
    mouse_hook_proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)(low_level_mouse_proc)
    # Set the hook for low-level mouse events (WH_MOUSE_LL, code 14)
    user32.SetWindowsHookExA(14, mouse_hook_proc, None, 0)
    # Standard message loop to keep processing messages related to the mouse events.
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(msg)
        user32.DispatchMessageA(msg)



def get_pressed_inputs(all_items:bool=False, include_xinputs:bool=True):
    # Get pressed keyboard inputs:
    # If 'all_items' is True, it checks the state of all keys
    # Otherwise, it checks only the keys that are currently being used
    inputs = tuple(
        keycode for keycode in (button_map.keyboard.keys() if all_items else used_inputs["inputs"].keys()) 
        if user32.GetAsyncKeyState(keycode) & 0x8000  # Check if the key is currently pressed
    )

    # If Xbox controller inputs should be included
    if include_xinputs:
        gamepad = get_xinput_state()  # Get the current state of the Xbox controller
        if gamepad != None:  # If the controller is connected
            # Append pressed Xbox controller inputs to the 'inputs' tuple
            inputs += tuple(
                value for key, value in button_map.controller.items() 
                if ((value in used_inputs["xinputs"].keys()) or all_items) and (
                    # Check for buttons pressed on the controller 
                    (isinstance(key, int) and (gamepad.Gamepad.wButtons & key)) or
                    # Check if left or right trigger is pressed
                    (value == "XI.lt" and gamepad.Gamepad.bLeftTrigger > 0) or 
                    (value == "XI.rt" and gamepad.Gamepad.bRightTrigger > 0)
                )
            )

    return inputs



def get_mouse_pos():
    pt = POINT()  # Create a POINT structure to hold the cursor's position
    if user32.GetCursorPos(ctypes.byref(pt)):  # Retrieve the cursor's position
        return (pt.x, pt.y)  # Return the x, y coordinates as a tuple
    return (0, 0)  # Return (0, 0) if the cursor position cannot be retrieved


def get_thumbstick_pos(right: bool=False):
    state = get_xinput_state()  # Get the current state of the Xbox controller
    if state == None:  
        return (0, 0)  # Return (0, 0) if the controller state cannot be retrieved
    
    if right:
        # Returns the right thumbsticks position adjusted for a small deadzone
        return (
            0 if -300 < state.Gamepad.sThumbRX < 300 else state.Gamepad.sThumbRX,
            0 if -300 < state.Gamepad.sThumbRY < 300 else state.Gamepad.sThumbRY
        )

    # By default, returns the left thumbsticks position adjusted for a small deadzone
    return (
        0 if -300 < state.Gamepad.sThumbLX < 300 else state.Gamepad.sThumbLX,
        0 if -300 < state.Gamepad.sThumbLY < 300 else state.Gamepad.sThumbLY
    )

        

def load_profile(profile_json: str):
    global profile, used_inputs 
    if not os_path.exists(profile_json):  # Check if the specified profile JSON file exists
        profiles = [f for f in os_listdir("profiles") if f.endswith('.json')]  # List all JSON profiles
        if profiles == []:  # If no profiles are found
            create_new_profile()  # Create a new profile
            return  # Exit the function
        edit_settings("loaded_profile", f"profiles\\{profiles[0]}")  # Load the first available profile
        return  # Exit the function

    with open(profile_json, "r") as f:  # Open the specified profile JSON file for reading
        profile = json_load(f)  # Load the JSON data into the profile variable

    # Initialize dictionaries for new used inputs and XInput mappings
    new_used_inputs = {}
    new_used_xinputs = {}

    # Load Azeron key mappings from the profile
    for key, values in profile["azeron_keys"].items():
        # Skip certain keys based on the selected keypad model
        if settings["model"] not in ["cyborg2"] and key in {"41"}:
            continue
        if settings["model"] not in ["cyborg", "cyborg2"] and key in {"36", "37", "38"}:
            continue
        if settings["model"] not in ["cyborg", "cyborg2", "classic"] and key in {"13", "18"}:
            continue
        
        for item in values:  # Iterate over the key mappings
            if isinstance(item, str):  # Check if the item is a string, (str:xinput, int:keybaord/mouse input)
                # Update the XInput dictionary for Azeron buttons
                if item in new_used_xinputs.keys():
                    new_used_xinputs[item].append(f"azeron_button_{key}")  # Append the key assigned to the buttons image
                else:
                    new_used_xinputs[item] = [f"azeron_button_{key}"]  # Create new with key assigned to the buttons image
            else:
                # Update the used inputs dictionary for Azeron buttons
                if item in new_used_inputs.keys():
                    new_used_inputs[item].append(f"azeron_button_{key}")  # Append the key assigned to the buttons image
                else:
                    new_used_inputs[item] = [f"azeron_button_{key}"]  # Create new with key assigned to the buttons image

    # Load mouse key mappings from the profile
    for key, values in profile["mouse_keys"].items():
        # Skip certain keys based on mouse settings
        if settings["mouse"] != "cyro" and key in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14", "15", "16", "17", "20", "22", "28", "29", "30", "31"}:
            continue
        if settings["mouse"] not in {"g403", "g502"} and key in {"right", "left", "middle", "forward", "back", "dpi"}:
            continue
        if settings["mouse"] != "g502" and key in {"g7", "g8", "g9", "sl", "sr"}:
            continue

        for item in values:  # Iterate over the key mappings
            if isinstance(item, str):  # Check if the item is a string
                # Update the XInput dictionary for mouse buttons
                if item in new_used_xinputs.keys():
                    new_used_xinputs[item].append(f"mouse_button_{key}") # Append the key assigned to the buttons image
                else:
                    new_used_xinputs[item] = [f"mouse_button_{key}"]  # Create new with key assigned to the buttons image
            else:
                # Update the used inputs dictionary for mouse buttons
                if item in new_used_inputs.keys():
                    new_used_inputs[item].append(f"mouse_button_{key}")  # Append the key assigned to the buttons image
                else:
                    new_used_inputs[item] = [f"mouse_button_{key}"]  # Create new with key assigned to the buttons image

    # Check and update movement keys for the keypads thumbstick
    if not isinstance(profile["stick"], str):
        used_inputs["movement_keys"]["azeron"]["forward"], used_inputs["movement_keys"]["azeron"]["left"], used_inputs["movement_keys"]["azeron"]["back"], used_inputs["movement_keys"]["azeron"]["right"] = [x for x in profile["stick"]]
        for item in profile["stick"]:  # Iterate through the keypad thumbstick values
            if item not in new_used_inputs.keys():
                new_used_inputs[item] = []  # Initialize if not present

    # Check and update movement keys for the mouse's thumbstick
    if not isinstance(profile["mouse_stick"], str):
        used_inputs["movement_keys"]["mouse"]["forward"], used_inputs["movement_keys"]["mouse"]["left"], used_inputs["movement_keys"]["mouse"]["back"], used_inputs["movement_keys"]["mouse"]["right"] = [x for x in profile["mouse_stick"]]
        for item in profile["mouse_stick"]:  # Iterate through the mouse thumbstickstick values
            if item not in new_used_inputs.keys():
                new_used_inputs[item] = []  # Initialize if not present

    # Update the used_inputs dictionary with the newly collected inputs, using deepcopy to avoid modifying original
    used_inputs["inputs"] = deepcopy(new_used_inputs) 
    used_inputs["xinputs"] = deepcopy(new_used_xinputs)
    # Update the state of used thumbsticks based on the new inputs
    set_used_thumbsticks()  


def save_profile(profile:dict):
    # Save the provided profile dictionary to a JSON file at the location specified in settings
    with open(f"{settings['loaded_profile']}", "w") as f:
        json_dump(profile, f)  # Write the profile data to the file in JSON format
    
    # Load the newly saved profile after saving it
    load_profile(settings["loaded_profile"])


def create_new_profile():
    file_path = f"profiles\\new-profile.json"
    i = 1
    
    # Check if a profile with the same name already exists; if so, increment the counter
    while os_path.exists(file_path):
        file_path = f"profiles\\new-profile{i}.json"  # Update file name to include the counter
        i += 1 
    
    # Create a new profile file
    with open(file_path, "w") as f:
        json_dump(empty_profile_template, f)  # Write the empty profile template to the new file
    
    # Update the settings to mark the newly created profile as the loaded profile
    edit_settings("loaded_profile", file_path)


def edit_settings(key:str, value:str):
    global settings
    
    # Update the settings dictionary with the new key-value pair
    settings[key] = value
    
    # Open the settings file
    with open("settings.json", "w") as f:
        json_dump(settings, f)  # Write the updated settings to the file
    
    # Check if the loaded profile setting is changed
    if key == "loaded_profile":
        load_profile(value)  # if so, load the new profile
    
    # Check if the mouse setting is changed
    if key == "mouse":
        set_used_thumbsticks()  # If so, update the used thumbstick cache



def input_handler(input:int|str, state:bool):
    # Check if the input is a string (indicating it refers to an XInput button)
    if isinstance(input, str):
        # Iterate through all keycodes associated with the XInput input
        for keycode in used_inputs["xinputs"][input]:
            # Set the visibility of the associated image in the app based on the state
            app.set_image_visibility(keycode, state)
    else:
        # If the input is not a string, assume it's an integer input (referring to keyboard/mouse inputs)
        for keycode in used_inputs["inputs"][input]:
            # Set the visibility of the associated image in the app based on the state
            app.set_image_visibility(keycode, state)



def set_used_thumbsticks():
    global used_inputs 

    # Set the left stick state based on the current profile and settings
    used_inputs["sticks"]["left"] = (
        profile["stick"] == "xinput-l" or  # Check if the keybad thumbstick is set to the left thumbstick
        (settings["mouse"] == "cyro" and profile["mouse_stick"] == "xinput-l")  # Check if the selected mouse it the cyro and its thumbstick is set to the left thumbstick
    )
    
    # Set the right stick state based on the current profile and settings
    used_inputs["sticks"]["right"] = (
        profile["stick"] == "xinput-r" or  # Check if the keybad thumbstick is set to the right thumbstick
        (settings["mouse"] == "cyro" and profile["mouse_stick"] == "xinput-r")  # Check if the selected mouse it the cyro and its thumbstick is set to the right thumbstick
    )


def wasd_handler(new_pressed_movement_keys:tuple, thumbstick_type:str="azeron"):
    global pressed_movement_keys

    # Initialize x and y movement values
    x, y = 0, 0

    # Update y based on the pressed movement keys for forward and back movement
    if used_inputs["movement_keys"][thumbstick_type]["forward"] in new_pressed_movement_keys:
        y += 1
    if used_inputs["movement_keys"][thumbstick_type]["back"] in new_pressed_movement_keys:
        y -= 1
    
    # Update x based on the pressed movement keys for right and left movement
    if used_inputs["movement_keys"][thumbstick_type]["right"] in new_pressed_movement_keys:
        x += 1
    if used_inputs["movement_keys"][thumbstick_type]["left"] in new_pressed_movement_keys:
        x -= 1
    
    # Determine thumbstick image ID based on thumbstick type
    if thumbstick_type == "azeron":
        thumbstick_image_id = "thumbstick_cap"
        #(394, 323) is the center position for the thumbstick cap
        if (x, y) == (0, 0):  # not moving
            x, y = 394, 323  # Center position
        elif (x, y) == (0, 1):  # forward
            x, y = 394, 300  # Move up
        elif (x, y) == (1, 1):  # forward right 
            x, y = 410, 307  # Move up and right
        elif (x, y) == (-1, 1):  # forward left 
            x, y = 378, 307  # Move up and left
        elif (x, y) == (1, 0):  # right
            x, y = 417, 323  # Move right
        elif (x, y) == (-1, 0):  # left
            x, y = 371, 323  # Move left
        elif (x, y) == (1, -1):  # back right 
            x, y = 410, 339  # Move down and right
        elif (x, y) == (-1, -1):  # back left 
            x, y = 378, 339  # Move down and left
        elif (x, y) == (0, -1):  # back
            x, y = 394, 346  # Move down
    else:
        thumbstick_image_id = "mouse_thumbstick_cap"
        #(533, 270) is the center position for the mouse thumbstick cap
        if (x, y) == (0, 0):  # not moving
            x, y = 533, 270  # Center position
        elif (x, y) == (0, 1):  # forward
            x, y = 533, 254  # Move up
        elif (x, y) == (1, 1):  # forward right 
            x, y = 544.5, 258.5  # Move up and right
        elif (x, y) == (-1, 1):  # forward left 
            x, y = 521.5, 258.5  # Move up and left
        elif (x, y) == (1, 0):  # right
            x, y = 549, 270  # Move right
        elif (x, y) == (-1, 0):  # left
            x, y = 517, 270  # Move left
        elif (x, y) == (1, -1):  # back right 
            x, y = 544.5, 281.5  # Move down and right
        elif (x, y) == (-1, -1):  # back left 
            x, y = 521.5, 281.5  # Move down and left
        elif (x, y) == (0, -1):  # back
            x, y = 533, 286  # Move down
    
    # Move the thumbstick cap image to the new (x, y) coordinates
    app.move_image(thumbstick_image_id, x, y) 
    # Update the pressed movement keys for the specified thumbstick type
    pressed_movement_keys[thumbstick_type] = new_pressed_movement_keys



i = 0
def main_input_loop():
    global i, mouse_speed_indicator, pressed_keys, mouse_pos, left_stick_pos, right_stick_pos, mouse_move_time
    
    while True:
        i += 1
        # Sleep for 10ms to control the loop speed
        sleep(0.01)  

        # Get the current time
        current_time = time()  

        # Get the currently pressed keys
        new_pressed_keys = get_pressed_inputs()
        
        # Handle key press events
        for key in tuple(set(new_pressed_keys) - set(pressed_keys)):  # Detect newly pressed keys
            input_handler(key, True)
        
        # Handle key release events
        for key in tuple(set(pressed_keys) - set(new_pressed_keys)):  # Detect released keys
            input_handler(key, False)
        
        # Update the pressed_keys to the newly pressed keys
        pressed_keys = tuple(new_pressed_keys)

        # Handle left stick movements
        if used_inputs["sticks"]["left"]:
            new_left_stick_pos = get_thumbstick_pos()  # Get the current position of the left thumbstick
            
            # Check if the position has changed
            if new_left_stick_pos != left_stick_pos:
                # Move the thumbstick cap based on the new position
                if profile["stick"] == "xinput-l":
                    app.move_image(
                        "thumbstick_cap",
                        394 + int(((new_left_stick_pos[0] - -32767) / (32767 - -32767)) * (23 - -23) + -23),
                        323 - int(((new_left_stick_pos[1] - -32767) / (32767 - -32767)) * (23 - -23) + -23)
                    )

                # Move the mouse thumbstick cap if using mouse stick profile
                if profile["mouse_stick"] == "xinput-l" and settings["mouse"] == "cyro":
                    app.move_image(
                        "mouse_thumbstick_cap",
                        533 + int(((new_left_stick_pos[0] - -32767) / (32767 - -32767)) * (17 - -17) + -17),
                        270 - int(((new_left_stick_pos[1] - -32767) / (32767 - -32767)) * (17 - -17) + -17)
                    )
                left_stick_pos = tuple(new_left_stick_pos)  # Update the stored left stick position
                
        # Handle right stick movements
        if used_inputs["sticks"]["right"]:
            new_right_stick_pos = get_thumbstick_pos(right=True)  # Get the current position of the right thumbstick
            
            # Check if the position has changed
            if new_right_stick_pos != right_stick_pos:
                # Move the thumbstick cap based on the new position
                if profile["stick"] == "xinput-r":
                    app.move_image(
                        "thumbstick_cap",
                        394 + int(((new_right_stick_pos[0] - -32767) / (32767 - -32767)) * (23 - -23) + -23),
                        323 - int(((new_right_stick_pos[1] - -32767) / (32767 - -32767)) * (23 - -23) + -23)
                    )

                # Move the mouse thumbstick cap if using mouse stick profile
                if profile["mouse_stick"] == "xinput-r" and settings["mouse"] == "cyro":
                    app.move_image(
                        "mouse_thumbstick_cap",
                        533 + int(((new_right_stick_pos[0] - -32767) / (32767 - -32767)) * (17 - -17) + -17),
                        270 - int(((new_right_stick_pos[1] - -32767) / (32767 - -32767)) * (17 - -17) + -17)
                    )
                right_stick_pos = tuple(new_right_stick_pos)  # Update the stored right stick position

        # Handle WASD movement keys for the Azeron
        if isinstance(profile["stick"], list):
            new_pressed_movement_keys = tuple(set(pressed_keys) & set(used_inputs["movement_keys"]["azeron"].values()))
            if new_pressed_movement_keys != pressed_movement_keys["azeron"]:
                wasd_handler(new_pressed_movement_keys)  # Call handler for WASD movement

        # Handle mouse movement keys if using the cyro mouse stick
        if (isinstance(profile["mouse_stick"], list) and settings["mouse"] == "cyro"):
            new_pressed_movement_keys = tuple(set(pressed_keys) & set(used_inputs["movement_keys"]["mouse"].values()))
            if new_pressed_movement_keys != pressed_movement_keys["mouse"]:
                wasd_handler(new_pressed_movement_keys, thumbstick_type="mouse")  # Call handler for mouse movement

        # Update mouse speed indicator every 5 iterations
        if i % 5 == 0:
            new_mouse_pos = get_mouse_pos()  # Get the current mouse position
            
            # Check if the position has changed
            if mouse_pos != new_mouse_pos:
                # Calculate speed and direction
                speed = math_sqrt((new_mouse_pos[0] - mouse_pos[0]) ** 2 + (new_mouse_pos[1] - mouse_pos[1]) ** 2) / max((current_time - mouse_move_time), 0.00001)
                direction = math_degrees(math_atan2((new_mouse_pos[1] - mouse_pos[1]), (new_mouse_pos[0] - mouse_pos[0])))
                
                # Normalize direction to be in the range of [0, 360)
                if direction < 0:
                    direction += 360

                # Cap speed at 15000
                if speed > 15000:
                    speed = 15000
                
                # Normalize speed to a range suitable for the application
                speed = int(((speed - 0) / (15000 - 0)) * (72 - 0) + 0)

                # Calculate new position for the movement indicator
                angle_rad = math_radians(direction)
                position = (int(639 + 72 * math_cos(angle_rad)), int(381 + 72 * math_sin(angle_rad)))

                # Move the movement indicator image
                app.move_image("movement_indicator", position[0], position[1])
                
                # If there is a mouse speed indicator, delete it
                if mouse_speed_indicator is not None:
                    app.canvas.delete(mouse_speed_indicator)
                    mouse_speed_indicator = None
                
                # Create a new mouse speed indicator line
                mouse_speed_indicator = app.canvas.create_line(
                    653, 395,
                    (653 + speed * math_cos(angle_rad)), 
                    (395 + speed * math_sin(angle_rad)), 
                    fill='white', width=5
                )

                # Update stored mouse position and time
                mouse_pos = tuple(new_mouse_pos)
                mouse_move_time = current_time
            else:
                # If mouse position hasn't changed, reset the movement indicator
                app.move_image("movement_indicator", 639, 381)
                if mouse_speed_indicator is not None:
                    app.canvas.delete(mouse_speed_indicator)
                    mouse_speed_indicator = None
            
            # Set mouse scroll images to invisible
            app.set_image_visibility("mouse_scroll_up", False)
            app.set_image_visibility("mouse_scroll_down", False)




class AzeronOverlayMainWindow:
    def __init__(self, root: tk.Tk):
        # Initialize lists and dictionaries for buttons and images
        self.button_edit_items = []
        self.set_button_labels = []
        self.thumbstick_wasd_buttons = []
        self.thumbstick_xinput_buttons = []
        self.images = {}
        self.new_profile = {}

        self.root = root
        self.root.title("AzBoard")  # Set the title of the window
        self.root.resizable(False, False)  # Make the window non-resizable

        # Create a menu bar
        self.menu_bar = tk.Menu(root)
        root.config(menu=self.menu_bar)

        # Create a profiles menu
        self.profiles_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_command(label="Settings", command=self.open_settings_window)
        self.menu_bar.add_cascade(label="Profiles", menu=self.profiles_menu)
        self.menu_bar.add_cascade(label="active profile", menu=None, command=None)

        # Create a canvas for drawing
        self.canvas = tk.Canvas(self.root, width=800, height=500, bg="#00ff00", borderwidth=0, highlightthickness=0)
        self.canvas.pack()

        self.update_profiles_menu()  # Update the profiles menu with available profiles

        self.create_mouse_overlay()  # Method to create mouse overlay elements
        self.create_azeron_overlay()  # Method to create Azeron overlay elements



    def open_settings_window(self):
        # Create a new settings window as a top-level window
        settings_window = tk.Toplevel(root)
        settings_window.title("Settings")  # Set the title of the settings window
        settings_window.geometry("300x200")  # Set the size of the window
        settings_window.grab_set()  # Ensure this window is modal and grabs all input
        settings_window.resizable(False, False)  # Prevent resizing of the window

        # Create a label and dropdown menu for selecting the model
        tk.Label(settings_window, text="Model:").pack(anchor="w", padx=10, pady=5)
        model_var = tk.StringVar(value=settings["model"])  # Initialize with current model setting
        model_menu = tk.OptionMenu(settings_window, model_var, "classic", "compact", "cyborg", "cyborg2")  # Create option menu
        model_menu.pack(anchor="w", padx=15)  # Pack the menu into the window

        # Create a label and dropdown menu for selecting the color
        tk.Label(settings_window, text="Color:").pack(anchor="w", padx=10, pady=5)
        color_var = tk.StringVar(value=settings["color"])  # Initialize with current color setting
        color_menu = tk.OptionMenu(settings_window, color_var, "black", "blue", "purple", "red", "baby-blue")  # Create option menu
        color_menu.pack(anchor="w", padx=15)  # Pack the menu into the window

        # Create a label and dropdown menu for selecting the mouse
        tk.Label(settings_window, text="Mouse:").pack(anchor="w", padx=10, pady=5)
        mouse_var = tk.StringVar(value=settings["mouse"])  # Initialize with current mouse setting
        mouse_menu = tk.OptionMenu(settings_window, mouse_var, "g403", "g502", "cyro")  # Create option menu
        mouse_menu.pack(anchor="w", padx=15)  # Pack the menu into the window

        # Function to handle saving settings and closing the window
        def delete_window():
            global settings  # Use global settings variable
            new_settings = deepcopy(settings)  # Create a copy of the current settings
            new_settings["model"] = model_var.get()  # Update model in new settings
            new_settings["color"] = color_var.get()  # Update color in new settings
            new_settings["mouse"] = mouse_var.get()  # Update mouse in new settings
            
            # Check if the new settings are different from the current settings
            if new_settings != settings:
                settings = deepcopy(new_settings)  # Update global settings variable
                with open("settings.json", "w") as f:  # Open settings file for writing
                    json_dump(new_settings, f)  # Save the new settings to the file

                # Refresh overlays after changing settings
                self.clear_images()  # Clear existing images
                self.create_azeron_overlay()  # Recreate the Azeron overlay
                self.create_mouse_overlay()  # Recreate the mouse overlay
                load_profile(settings["loaded_profile"])  # Load the active profile with updated settings

            settings_window.destroy()  # Close the settings window

        settings_window.protocol("WM_DELETE_WINDOW", delete_window)  # Set the close protocol for the window


    def button_edit_stuff(self, button: str, button_type: str):
        # Destroy all existing items in button_edit_items
        for item in self.button_edit_items:
            try:
                item.destroy()  # Attempt to destroy the item
            except:
                pass  # Ignore any errors that occur during destruction
        self.button_edit_items = []  # Clear the button_edit_items list

        # Destroy all existing items in thumbstick_wasd_buttons
        for item in self.thumbstick_wasd_buttons:
            try:
                item.destroy()  # Attempt to destroy the item
            except:
                pass  # Ignore any errors that occur during destruction
        self.thumbstick_wasd_buttons = []  # Clear the thumbstick_wasd_buttons list

        # Destroy all existing items in thumbstick_xinput_buttons
        for item in self.thumbstick_xinput_buttons:
            try:
                item.destroy()  # Attempt to destroy the item
            except:
                pass  # Ignore any errors that occur during destruction
        self.thumbstick_xinput_buttons = []  # Clear the thumbstick_xinput_buttons list

        # Destroy all existing items in set_button_labels
        for item in self.set_button_labels:
            try:
                item.destroy()  # Attempt to destroy the item
            except:
                pass  # Ignore any errors that occur during destruction
        self.set_button_labels = []  # Clear the set_button_labels list

        # Set the label text based on the button pressed
        if button == "sl":
            text = f"{button_type}: scroll left"  # Define text for scroll left action
        elif button == "sr":
            text = f"{button_type}: scroll right"  # Define text for scroll right action
        else:
            text = f"{button_type}: {button}"  # Define text for other button actions

        # Create a label to display the current button action
        label = tk.Label(self.edit_profile_window, text=text)
        label.place(x=1, y=282)  # Position the label in the window
        self.button_edit_items.append(label)  # Add the label to the button_edit_items list



        def update_item_button(key_type: str, key_name: str, old_name: str, listbox_index: int):
            key = ()  # Initialize an empty tuple to store the pressed key
            label = tk.Label(self.edit_profile_window, text="Press Something...", font=("Arial", 27))  # Create a label for user instruction
            label.place(x=150, y=402)  # Place the label in the window
            self.set_button_labels.append(label)  # Add the label to the set_button_labels list
            
            # Wait for a key press
            while key == ():
                sleep(0.001)  # Sleep briefly to avoid busy waiting
                key = get_pressed_inputs(all_items=True)  # Get the pressed key
            key = key[0]  # Retrieve the first key pressed

            # Destroy existing labels
            for item in self.set_button_labels:
                item.destroy()
            self.set_button_labels = []  # Clear the set_button_labels list

            # Update new_profile with the new key
            if old_name == "empty":
                self.new_profile[key_type][key_name].append(key)  # If the old name is empty, append the new key
            else:
                # Replace the old key with the new key in new_profile
                self.new_profile[key_type][key_name] = [key if x == old_name else x for x in self.new_profile[key_type][key_name]]
            
            listbox.delete(listbox_index)  # Remove the old item from the listbox

            # Handle the key and update the listbox
            if isinstance(key, str):
                pass  # If the key is a string, do nothing
            else:
                key = button_map.keyboard[key]  # Map the key using button_map
            listbox.insert(listbox_index, key)  # Insert the new key into the listbox

            # Clean up button edit items
            self.button_edit_items.remove(self.record_button)
            self.record_button.destroy()  # Destroy the record button
            self.delete_button.destroy()  # Destroy the delete button


        def delete_item_button(index: int, key_type: str, key_name: str, selected_item: str):
            listbox.delete(index)  # Delete the selected item from the listbox
            if selected_item != "empty":
                # Remove the corresponding key from new_profile
                self.new_profile[key_type][key_name].remove(get_key_from_value(button_map.keyboard, selected_item))
            
            # Clean up button edit items
            self.button_edit_items.remove(self.delete_button)
            self.record_button.destroy()  # Destroy the record button
            self.delete_button.destroy()  # Destroy the delete button


        def on_select(event: tk.Event):
            listbox = event.widget  # Get the listbox that triggered the event
            index = listbox.curselection()  # Get the index of the selected item
            if not index:  # If no item is selected, exit
                return
            
            selected_item = listbox.get(index)  # Get the selected item
            key_type, key_name = listbox._name.split("|")  # Extract key_type and key_name from the listbox name

            # Create the record button to set a new key
            self.record_button = tk.Button(self.edit_profile_window, text="Set Key", width=10, height=5, 
                                        command=lambda: Thread(target=update_item_button, args=(key_type, key_name, 
                                        get_key_from_value(button_map.keyboard, selected_item), index)).start())
            self.record_button.place(x=150, y=282)  # Place the button in the window
            self.button_edit_items.append(self.record_button)  # Add the button to the button_edit_items list

            # Create the delete button
            self.delete_button = tk.Button(self.edit_profile_window, text="Delete", width=16, 
                                        command=lambda: delete_item_button(index, key_type, key_name, selected_item))
            self.delete_button.place(x=1, y=470)  # Place the button in the window
            self.button_edit_items.append(self.delete_button)  # Add the button to the button_edit_items list


        def change_movement_buttons(index: int, old_keycode: int, button: tk.Button):
            key = ()  # Initialize an empty tuple to store the pressed key
            label = tk.Label(self.edit_profile_window, text="Press a key...", font=("Arial", 27))  # Create a label for user instruction
            label.place(x=150, y=402)  # Place the label in the window
            self.set_button_labels.append(label)  # Add the label to the set_button_labels list
            
            # Wait for a key press
            while key == ():
                sleep(0.001)  # Sleep briefly to avoid busy waiting
                key = get_pressed_inputs(all_items=True, include_xinputs=False)  # Get the pressed key without XInput
            key = key[0]  # Retrieve the first key pressed

            # Destroy existing labels
            for item in self.set_button_labels:
                item.destroy()
            self.set_button_labels = []  # Clear the set_button_labels list

            # Check if the new key is the same as the old keycode
            if key == old_keycode:
                return  # If they are the same, exit
            self.new_profile[self.thumbstick_key][index] = key  # Update the new profile with the new key
            button.config(text=button_map.keyboard[key])  # Update the button text


        def change_thumbstick():
            # Check if the selected thumbstick is the same as the current profile
            if self.active_thumbstick.get() == self.new_profile[self.thumbstick_key]:
                return
            self.new_profile[self.thumbstick_key] = self.active_thumbstick.get()  # Update the new profile with the selected thumbstick


        def toggle_thumbstick():
            # If the selected stick type is "Keyboard"
            if self.stick_type.get() == "Keyboard":
                if isinstance(self.new_profile[self.thumbstick_key], list):
                    return  # If it's already a list, exit

                # Destroy existing thumbstick buttons
                for item in self.thumbstick_xinput_buttons:
                    try:
                        item.destroy()  # Attempt to destroy the item
                    except:
                        pass  # Ignore any errors that occur during destruction
                self.thumbstick_xinput_buttons = []  # Clear the thumbstick_xinput_buttons list

                # Set default keys for WASD
                self.new_profile[self.thumbstick_key] = [87, 65, 83, 68]  # WASD keys

                # Create buttons and labels for each direction
                label = tk.Label(self.edit_profile_window, text="Up:")
                label.place(x=7, y=360)  # Position the label
                self.thumbstick_wasd_buttons.append(label)  # Add the label to the buttons list
                up_button = tk.Button(self.edit_profile_window, text="KB.w", command=lambda: Thread(target=change_movement_buttons, args=(0, self.new_profile[self.thumbstick_key][0], up_button)).start())
                up_button.place(x=46, y=360)  # Place the button in the window
                self.thumbstick_wasd_buttons.append(up_button)  # Add the button to the buttons list

                # Repeat for left, down, and right
                label = tk.Label(self.edit_profile_window, text="Left:")
                label.place(x=7, y=390)
                self.thumbstick_wasd_buttons.append(label)
                left_button = tk.Button(self.edit_profile_window, text="KB.a", command=lambda: Thread(target=change_movement_buttons, args=(1, self.new_profile[self.thumbstick_key][1], left_button)).start())
                left_button.place(x=46, y=390)
                self.thumbstick_wasd_buttons.append(left_button)

                label = tk.Label(self.edit_profile_window, text="Down:")
                label.place(x=7, y=420)
                self.thumbstick_wasd_buttons.append(label)
                down_button = tk.Button(self.edit_profile_window, text="KB.s", command=lambda: Thread(target=change_movement_buttons, args=(2, self.new_profile[self.thumbstick_key][2], down_button)).start())
                down_button.place(x=46, y=420)
                self.thumbstick_wasd_buttons.append(down_button)

                label = tk.Label(self.edit_profile_window, text="Right:")
                label.place(x=7, y=450)
                self.thumbstick_wasd_buttons.append(label)
                right_button = tk.Button(self.edit_profile_window, text="KB.d", command=lambda: Thread(target=change_movement_buttons, args=(3, self.new_profile[self.thumbstick_key][3], right_button)).start())
                right_button.place(x=46, y=450)
                self.thumbstick_wasd_buttons.append(right_button)

            else:
                # If the selected stick type is not "Keyboard"
                if isinstance(self.new_profile[self.thumbstick_key], str):
                    return  # If it's already a string, exit

                # Destroy existing WASD buttons
                for item in self.thumbstick_wasd_buttons:
                    try:
                        item.destroy()  # Attempt to destroy the item
                    except:
                        pass  # Ignore any errors that occur during destruction
                self.thumbstick_wasd_buttons = []  # Clear the thumbstick_wasd_buttons list

                # Set default value for the thumbstick
                self.new_profile[self.thumbstick_key] = "xinput-l"  # Set to left XInput stick
                self.active_thumbstick = tk.StringVar(value="xinput-l")


        if button == "thumbstick":
            # Determine the key associated with the thumbstick based on button type
            if button_type == "keypad":
                self.thumbstick_key = "stick"  # For keypad input
            else:
                self.thumbstick_key = "mouse_stick"  # For mouse input
            
            # Label for selecting input mode
            label = tk.Label(self.edit_profile_window, text="Select Input Mode:")
            label.place(x=1, y=300)  # Position the label
            self.button_edit_items.append(label)  # Keep track of created items

            # Check if the thumbstick type is a string (indicating XInput)
            if isinstance(self.new_profile[self.thumbstick_key], str):
                self.stick_type = tk.StringVar(value="XInput")  # Default to XInput
                self.active_thumbstick = tk.StringVar(value=self.new_profile[self.thumbstick_key])
                
                # Radio buttons for selecting left or right thumbstick
                left_stick_button = tk.Radiobutton(self.edit_profile_window, text="Left", variable=self.active_thumbstick, value="xinput-l", command=change_thumbstick)
                right_stick_button = tk.Radiobutton(self.edit_profile_window, text="Right", variable=self.active_thumbstick, value="xinput-r", command=change_thumbstick)
                
                # Create windows for the radio buttons
                self.edit_profile_canvas.create_window(7, 380, anchor=tk.NW, window=left_stick_button)
                self.edit_profile_canvas.create_window(7, 400, anchor=tk.NW, window=right_stick_button)
                self.thumbstick_xinput_buttons.append(left_stick_button)  # Store button references
                self.thumbstick_xinput_buttons.append(right_stick_button)
            else:
                self.stick_type = tk.StringVar(value="Keyboard")  # Default to keyboard
                
                # Create labels and buttons for keyboard controls (WASD)
                label = tk.Label(self.edit_profile_window, text="Up:")
                label.place(x=7, y=360)
                self.thumbstick_wasd_buttons.append(label)
                up_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][0]], 
                                    command=lambda: Thread(target=change_movement_buttons, args=(0, self.new_profile[self.thumbstick_key][0], up_button)).start())
                up_button.place(x=46, y=360)
                self.thumbstick_wasd_buttons.append(up_button)

                # Repeat for Left, Down, Right controls
                label = tk.Label(self.edit_profile_window, text="Left:")
                label.place(x=7, y=390)
                self.thumbstick_wasd_buttons.append(label)
                left_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][1]], 
                                        command=lambda: Thread(target=change_movement_buttons, args=(1, self.new_profile[self.thumbstick_key][1], left_button)).start())
                left_button.place(x=46, y=390)
                self.thumbstick_wasd_buttons.append(left_button)

                label = tk.Label(self.edit_profile_window, text="Down:")
                label.place(x=7, y=420)
                self.thumbstick_wasd_buttons.append(label)
                down_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][2]], 
                                        command=lambda: Thread(target=change_movement_buttons, args=(2, self.new_profile[self.thumbstick_key][2], down_button)).start())
                down_button.place(x=46, y=420)
                self.thumbstick_wasd_buttons.append(down_button)

                label = tk.Label(self.edit_profile_window, text="Right:")
                label.place(x=7, y=450)
                self.thumbstick_wasd_buttons.append(label)
                right_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][3]], 
                                        command=lambda: Thread(target=change_movement_buttons, args=(3, self.new_profile[self.thumbstick_key][3], right_button)).start())
                right_button.place(x=46, y=450)
                self.thumbstick_wasd_buttons.append(right_button)

            # Radio buttons for toggling between XInput and Keyboard input modes
            xinput_button = tk.Radiobutton(self.edit_profile_window, text="XInput", variable=self.stick_type, value="XInput", command=toggle_thumbstick)
            keyboard_button = tk.Radiobutton(self.edit_profile_window, text="Keyboard", variable=self.stick_type, value="Keyboard", command=toggle_thumbstick)
            
            # Create windows for the radio buttons
            self.edit_profile_canvas.create_window(1, 320, anchor=tk.NW, window=xinput_button)
            self.edit_profile_canvas.create_window(1, 340, anchor=tk.NW, window=keyboard_button)
            self.button_edit_items.append(xinput_button)  # Store button references
            self.button_edit_items.append(keyboard_button)

        else:
            # Determine the key type based on button type (mouse or Azeron)
            if button_type == "mouse":
                key_type = "mouse_keys"
            else:
                key_type = "azeron_keys"
            
            # Create a listbox for displaying current button mappings
            listbox = tk.Listbox(self.edit_profile_window, name=f"{key_type}|{button}")
            for item in self.new_profile[key_type][button]:
                if item in button_map.keyboard.keys():
                    listbox.insert(tk.END, button_map.keyboard[item])  # Insert mapped keys
                else:
                    listbox.insert(tk.END, item)  # Insert item directly if not in keyboard map

            self.edit_profile_canvas.create_window(1, 302, anchor=tk.NW, window=listbox)  # Create window for the listbox
            listbox.bind("<<ListboxSelect>>", on_select)  # Bind selection event to the listbox
            add_button = tk.Button(self.edit_profile_window, text="+", width=2, command=lambda: listbox.insert(tk.END, "empty"))  # Button to add an empty entry
            add_button.place(x=100, y=282)
            self.button_edit_items.append(listbox)  # Store listbox reference
            self.button_edit_items.append(add_button)  # Store add button reference



    def open_profile_edit_window(self):
        self.edit_profile_window = tk.Toplevel(root)
        self.edit_profile_window.title("Profile Edit")
        self.edit_profile_window.geometry("750x500")
        self.edit_profile_window.grab_set()
        self.edit_profile_window.resizable(False, False)
        self.edit_profile_canvas = tk.Canvas(self.edit_profile_window, width=750, height=500)
        self.edit_profile_canvas.pack(fill=tk.BOTH, expand=True)
        if self.new_profile == {}:
            self.new_profile = deepcopy(profile)

        
        menu_bar = tk.Menu(self.edit_profile_window)
        self.edit_profile_window.config(menu=menu_bar)

        
        def clear_profile():
            self.new_profile = deepcopy(empty_profile_template)
            for item in self.button_edit_items:
                try:
                    item.destroy()
                except:
                    pass

            for item in self.thumbstick_wasd_buttons:
                try:
                    item.destroy()
                except:
                    pass
            self.thumbstick_wasd_buttons = []
            self.button_edit_items = []

        clear_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Clear", menu=clear_menu)
        clear_menu1 = tk.Menu(clear_menu, tearoff=0)
        clear_menu.add_cascade(label="you sure?", menu=clear_menu1)
        clear_menu1.add_command(label="yes", command=clear_profile)
        
        def on_enter(event):
            entered_text = entry.get()
            if entered_text.lower() in ["con", "prn", "aux", "nul", "com1", "com9", "lpt1", "lpt9"]:
                return 
            if entered_text == "":
                return
            if entered_text == settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""):
                return
            
            os_rename(settings["loaded_profile"], f"profiles\\{entered_text}.json")
            edit_settings("loaded_profile", f"profiles\\{entered_text}.json")
            self.update_profiles_menu()

        entry = tk.Entry(self.edit_profile_window, validate='key', validatecommand=(root.register(lambda new_value: all(char not in new_value for char in ['\\', '/', '.', '\'', '"', '<', '>', '|', '?', '*', ':']) and len(new_value) < 45 ), '%P'))
        entry.insert(0, settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""))
        entry.place(x=300, y=1)
        entry.bind("<Return>", on_enter)

        
        self.set_image_visibility("azeron_edit_base", True)
        self.set_image_visibility("azeron_edit_classic", True)
        self.set_image_visibility("azeron_edit_cyborg", True)
        self.set_image_visibility("azeron_edit_cyborg2", True)
        self.set_image_visibility("azeron_edit_classic_20", True)
        self.set_image_visibility("cyro_edit_base", True)
        
        def delete_window():
            self.set_image_visibility("azeron_edit_base", False)
            self.set_image_visibility("azeron_edit_classic", False)
            self.set_image_visibility("azeron_edit_cyborg", False)
            self.set_image_visibility("azeron_edit_cyborg2", False)
            self.set_image_visibility("azeron_edit_classic_20", False)
            self.set_image_visibility("cyro_edit_base", False)
            if self.new_profile != {} and self.new_profile != profile:
                save_profile(self.new_profile)
            self.new_profile = {}
            self.edit_profile_window.destroy()
        self.edit_profile_window.protocol("WM_DELETE_WINDOW", delete_window)

        #mouse
        tk.Label(self.edit_profile_window, text="Mouse").place(x=605, y=10)
        if settings["mouse"] == "g403":
            tk.Button(self.edit_profile_window, text="left",    command=lambda: self.button_edit_stuff("left",   "mouse"), width=6, height=6).place(x=550, y=40)
            tk.Button(self.edit_profile_window, text="middle",  command=lambda: self.button_edit_stuff("middle", "mouse"), width=5, height=2).place(x=603, y=60)
            tk.Button(self.edit_profile_window, text="dpi",     command=lambda: self.button_edit_stuff("dpi",    "mouse"), width=4, height=2).place(x=606, y=110)
            tk.Button(self.edit_profile_window, text="right",   command=lambda: self.button_edit_stuff("right",  "mouse"), width=6, height=6).place(x=650, y=40)
            
            tk.Button(self.edit_profile_window, text="↑", command=lambda: self.button_edit_stuff("forward", "mouse"), width=3, height=2).place(x=560, y=145)
            tk.Button(self.edit_profile_window, text="↓", command=lambda: self.button_edit_stuff("back",    "mouse"), width=3, height=2).place(x=560, y=185)
        elif settings["mouse"] == "g502":
            tk.Button(self.edit_profile_window, text="left",    command=lambda: self.button_edit_stuff("left",   "mouse"), width=6, height=6).place(x=550, y=40)
            tk.Button(self.edit_profile_window, text="G8",      command=lambda: self.button_edit_stuff("g8",     "mouse"), width=3, height=2).place(x=520, y=40)
            tk.Button(self.edit_profile_window, text="G7",      command=lambda: self.button_edit_stuff("g7",     "mouse"), width=3, height=2).place(x=520, y=80)

            tk.Button(self.edit_profile_window, text="middle",  command=lambda: self.button_edit_stuff("middle", "mouse"), width=5, height=2).place(x=619, y=60)
            tk.Button(self.edit_profile_window, text="G9",      command=lambda: self.button_edit_stuff("g9",     "mouse"), width=4, height=2).place(x=622, y=110)
            
            tk.Button(self.edit_profile_window, text="←",      command=lambda: self.button_edit_stuff("sl",     "mouse"), width=1, height=2).place(x=602, y=60)
            tk.Button(self.edit_profile_window, text="→",      command=lambda: self.button_edit_stuff("sr",     "mouse"), width=1, height=2).place(x=662, y=60)
            tk.Button(self.edit_profile_window, text="right",   command=lambda: self.button_edit_stuff("right",  "mouse"), width=6, height=6).place(x=678, y=40)
            
            tk.Button(self.edit_profile_window, text="↑",   command=lambda: self.button_edit_stuff("forward", "mouse"), width=3, height=2).place(x=560, y=145)
            tk.Button(self.edit_profile_window, text="↓",   command=lambda: self.button_edit_stuff("back",    "mouse"), width=3, height=2).place(x=560, y=185)
            tk.Button(self.edit_profile_window, text="dpi", command=lambda: self.button_edit_stuff("dpi",     "mouse"), width=4, height=2).place(x=520, y=145)

        elif settings["mouse"] == "cyro":
            tk.Button(self.edit_profile_window, text="4",    command=lambda: self.button_edit_stuff("4",   "mouse"), width=5, height=2).place(x=525, y=55)
            tk.Button(self.edit_profile_window, text="3",    command=lambda: self.button_edit_stuff("3",   "mouse"), width=5, height=2).place(x=575, y=55)
            tk.Button(self.edit_profile_window, text="2",    command=lambda: self.button_edit_stuff("2",   "mouse"), width=5, height=2).place(x=625, y=55)
            tk.Button(self.edit_profile_window, text="1",    command=lambda: self.button_edit_stuff("1",   "mouse"), width=5, height=2).place(x=675, y=55)
            
            tk.Button(self.edit_profile_window, text="8",    command=lambda: self.button_edit_stuff("8",   "mouse"), width=5, height=2).place(x=525, y=100)
            tk.Button(self.edit_profile_window, text="7",    command=lambda: self.button_edit_stuff("7",   "mouse"), width=5, height=2).place(x=575, y=100)
            tk.Button(self.edit_profile_window, text="6",    command=lambda: self.button_edit_stuff("6",   "mouse"), width=5, height=2).place(x=625, y=100)
            tk.Button(self.edit_profile_window, text="5",    command=lambda: self.button_edit_stuff("5",   "mouse"), width=5, height=2).place(x=675, y=100)
            
            tk.Button(self.edit_profile_window, text="12",    command=lambda: self.button_edit_stuff("12",   "mouse"), width=5, height=2).place(x=550, y=145)
            tk.Button(self.edit_profile_window, text="11",    command=lambda: self.button_edit_stuff("11",   "mouse"), width=5, height=2).place(x=600, y=145)
            tk.Button(self.edit_profile_window, text="10",    command=lambda: self.button_edit_stuff("10",   "mouse"), width=5, height=2).place(x=650, y=145)
            tk.Button(self.edit_profile_window, text="9",     command=lambda: self.button_edit_stuff("9",    "mouse"), width=5, height=2).place(x=700, y=145)
            
            tk.Button(self.edit_profile_window, text="17",    command=lambda: self.button_edit_stuff("17",   "mouse"), width=5, height=2).place(x=550, y=190)
            tk.Button(self.edit_profile_window, text="16",    command=lambda: self.button_edit_stuff("16",   "mouse"), width=5, height=2).place(x=600, y=190)
            tk.Button(self.edit_profile_window, text="15",    command=lambda: self.button_edit_stuff("15",   "mouse"), width=5, height=2).place(x=650, y=190)
            tk.Button(self.edit_profile_window, text="14",    command=lambda: self.button_edit_stuff("14",   "mouse"), width=5, height=2).place(x=700, y=190)
            
            tk.Button(self.edit_profile_window, text="thumbstick", command=lambda: self.button_edit_stuff("thumbstick", "mouse"), width=8, height=3).place(x=455, y=146)
            tk.Button(self.edit_profile_window, text="22",         command=lambda: self.button_edit_stuff("22",         "mouse"), width=8, height=1).place(x=455, y=205)

            tk.Button(self.edit_profile_window, text="31", command=lambda: self.button_edit_stuff("31", "mouse"), width=2, height=1).place(x=475, y=115)#down
            tk.Button(self.edit_profile_window, text="20", command=lambda: self.button_edit_stuff("20", "mouse"), width=2, height=1).place(x=475, y=90)#middle
            tk.Button(self.edit_profile_window, text="29", command=lambda: self.button_edit_stuff("29", "mouse"), width=2, height=1).place(x=475, y=65) #up
            tk.Button(self.edit_profile_window, text="30", command=lambda: self.button_edit_stuff("30", "mouse"), width=2, height=1).place(x=452, y=90)#left
            tk.Button(self.edit_profile_window, text="28", command=lambda: self.button_edit_stuff("28", "mouse"), width=2, height=1).place(x=498, y=90)#right


        '''
        x:
         1: 10
         2: 60
         3: 110
         4: 160
         5: 210
         6: 260

        y:
         1: 10
         2: 55:
         3: 100
         4: 145
         5: 190
         6: 235

        '''

        #base
        tk.Label(self.edit_profile_window, text="Keypad").place(x=105, y=10)
        tk.Button(self.edit_profile_window, text="4",  command=lambda: self.button_edit_stuff("4",  "keypad"), width=5, height=2).place(x=60, y=55)
        tk.Button(self.edit_profile_window, text="8",  command=lambda: self.button_edit_stuff("8",  "keypad"), width=5, height=2).place(x=110, y=55)
        tk.Button(self.edit_profile_window, text="12", command=lambda: self.button_edit_stuff("12", "keypad"), width=5, height=2).place(x=160, y=55)
        tk.Button(self.edit_profile_window, text="17", command=lambda: self.button_edit_stuff("17", "keypad"), width=5, height=2).place(x=210, y=55)

        tk.Button(self.edit_profile_window, text="3",  command=lambda: self.button_edit_stuff("3",  "keypad"), width=5, height=2).place(x=60, y=100)
        tk.Button(self.edit_profile_window, text="7",  command=lambda: self.button_edit_stuff("7",  "keypad"), width=5, height=2).place(x=110, y=100)
        tk.Button(self.edit_profile_window, text="11", command=lambda: self.button_edit_stuff("11", "keypad"), width=5, height=2).place(x=160, y=100)
        tk.Button(self.edit_profile_window, text="16", command=lambda: self.button_edit_stuff("16", "keypad"), width=5, height=2).place(x=210, y=100)
        
        tk.Button(self.edit_profile_window, text="2",  command=lambda: self.button_edit_stuff("2",  "keypad"), width=5, height=2).place(x=60, y=145)
        tk.Button(self.edit_profile_window, text="6",  command=lambda: self.button_edit_stuff("6",  "keypad"), width=5, height=2).place(x=110, y=145)
        tk.Button(self.edit_profile_window, text="10", command=lambda: self.button_edit_stuff("10", "keypad"), width=5, height=2).place(x=160, y=145)
        tk.Button(self.edit_profile_window, text="15", command=lambda: self.button_edit_stuff("15", "keypad"), width=5, height=2).place(x=210, y=145)
        tk.Button(self.edit_profile_window, text="19", command=lambda: self.button_edit_stuff("19", "keypad"), width=5, height=2).place(x=260, y=145)
        
        tk.Button(self.edit_profile_window, text="1",  command=lambda: self.button_edit_stuff("1",  "keypad"), width=5, height=2).place(x=60, y=190)
        tk.Button(self.edit_profile_window, text="5",  command=lambda: self.button_edit_stuff("5",  "keypad"), width=5, height=2).place(x=110, y=190)
        tk.Button(self.edit_profile_window, text="9",  command=lambda: self.button_edit_stuff("9",  "keypad"), width=5, height=2).place(x=160, y=190)
        tk.Button(self.edit_profile_window, text="14", command=lambda: self.button_edit_stuff("14", "keypad"), width=5, height=2).place(x=210, y=190)
        
        tk.Button(self.edit_profile_window, text="thumbstick", command=lambda: self.button_edit_stuff("thumbstick", "keypad"), width=10, height=4).place(x=318, y=154)

        tk.Button(self.edit_profile_window, text="23", command=lambda: self.button_edit_stuff("23", "keypad"), width=5, height=2).place(x=310, y=230)
        tk.Button(self.edit_profile_window, text="20", command=lambda: self.button_edit_stuff("20", "keypad"), width=5, height=2).place(x=360, y=230)
        

        tk.Button(self.edit_profile_window, text="31", command=lambda: self.button_edit_stuff("31", "keypad"), width=3, height=1).place(x=345, y=125)#down
        tk.Button(self.edit_profile_window, text="22", command=lambda: self.button_edit_stuff("22", "keypad"), width=3, height=1).place(x=345, y=100)#middle
        tk.Button(self.edit_profile_window, text="29", command=lambda: self.button_edit_stuff("29", "keypad"), width=3, height=1).place(x=345, y=75) #up
        tk.Button(self.edit_profile_window, text="30", command=lambda: self.button_edit_stuff("30", "keypad"), width=3, height=1).place(x=315, y=100)#left
        tk.Button(self.edit_profile_window, text="28", command=lambda: self.button_edit_stuff("28", "keypad"), width=3, height=1).place(x=375, y=100)#right


        if "cyborg" in settings["model"]:
            #cyborg
            tk.Button(self.edit_profile_window, text="37", command=lambda: self.button_edit_stuff("37", "keypad"), width=5, height=2).place(x=60, y=235)
            tk.Button(self.edit_profile_window, text="38", command=lambda: self.button_edit_stuff("38", "keypad"), width=5, height=2).place(x=110, y=235)
            tk.Button(self.edit_profile_window, text="13", command=lambda: self.button_edit_stuff("13", "keypad"), width=5, height=2).place(x=160, y=235)
            tk.Button(self.edit_profile_window, text="18", command=lambda: self.button_edit_stuff("18", "keypad"), width=5, height=2).place(x=210, y=235)
            tk.Button(self.edit_profile_window, text="36", command=lambda: self.button_edit_stuff("36", "keypad"), width=5, height=2).place(x=10, y=145)
            if settings["model"] == "cyborg2":
                #cyborg2
                tk.Button(self.edit_profile_window, text="41", command=lambda: self.button_edit_stuff("41", "keypad"), width=3, height=2).place(x=410, y=230)
        elif settings["model"] == "classic":
            #classic
            tk.Button(self.edit_profile_window, text="13", command=lambda: self.button_edit_stuff("13", "keypad"), width=5, height=2).place(x=160, y=10)
            tk.Button(self.edit_profile_window, text="18", command=lambda: self.button_edit_stuff("18", "keypad"), width=5, height=2).place(x=210, y=10)

        self.edit_profile_canvas.create_line(0, 280, 750, 280, width=3, fill="black")
      

    def update_profiles_menu(self):
        # Clear the existing profiles menu
        self.profiles_menu.delete(0, tk.END)

        # Create a submenu for profiles
        profiles_submenu = tk.Menu(self.profiles_menu, tearoff=0)

        # Add a button to create a new profile
        profiles_submenu.add_command(label="new...", command=lambda: (create_new_profile(), self.update_profiles_menu())) #make new empty profile
        # Populate the menu with the available profiles
        for profile_name in [f[:-5] for f in os_listdir("profiles") if f.endswith('.json')]:
            if profile_name == settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""):# Excluse the currently selected profile
                continue 
            profiles_submenu.add_command(label=profile_name, command=lambda p=profile_name: (edit_settings("loaded_profile", f"profiles\\{p}.json"), self.update_profiles_menu()))

        # Add the profiles submenu with the current profile highlighted
        self.profiles_menu.add_cascade(label=f"{settings['loaded_profile'].replace('profiles\\', '').replace('.json', '')}", menu=profiles_submenu)

        # Add the Edit option
        self.profiles_menu.add_command(label="Edit", command=self.open_profile_edit_window)
        
        # Button to delete a profile
        def delete_profile(profile_name):
            # Check if the profile exists
            if not os_path.exists(profile_name):
                return
            # If so, delete the profile, and load a random profile
            os_remove(profile_name)
            edit_settings("loaded_profile", f"profiles\\{[f for f in os_listdir("profiles") if f.endswith('.json')][0]}")
            self.update_profiles_menu()
        
        # Check if there is more than 1 profile
        if len([f for f in os_listdir("profiles") if f.endswith('.json')]) >= 2:
            #If so, Add a delete button
            delete_menu_1 = tk.Menu(self.profiles_menu, tearoff=0)
            self.profiles_menu.add_cascade(label="Delete", menu=delete_menu_1)
            delete_menu_2 = tk.Menu(self.profiles_menu, tearoff=0)
            delete_menu_1.add_cascade(label="you sure?", menu=delete_menu_2)
            delete_menu_2.add_command(label="yes", command=lambda:delete_profile(settings["loaded_profile"]))

        # Add a third item to the main menu to display the current profile
        self.menu_bar.entryconfig(3, label=settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""))



    def clear_images(self):
        # Remove all images from the window
        for key, value in dict(self.images).items():
            self.canvas.delete(value[1])
            del self.images[key]


    def create_mouse_overlay(self):
        # Create the mouse overlay
        # Check if the selected mouse is the g403
        if settings["mouse"] == "g403":
            # If so, Create the g403 Overlay
            self.add_overlay_image("assets\\mouse\\g403\\base.png", "mouse_base")
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\left.png", "mouse_button_left", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\right.png", "mouse_button_right", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\middle.png", "mouse_button_middle", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\dpi.png", "mouse_button_dpi", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\forward.png", "mouse_button_forward", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\back.png", "mouse_button_back", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\scroll_down.png", "mouse_scroll_down", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\scroll_up.png", "mouse_scroll_up", visible=False)
        # Check if the selected mouse is the g502
        elif settings["mouse"] == "g502":
            # If so, Create the g502 Overlay
            self.add_overlay_image("assets\\mouse\\g502\\base.png", "mouse_base")
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\left.png", "mouse_button_left", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\right.png", "mouse_button_right", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\middle.png", "mouse_button_middle", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\dpi.png", "mouse_button_dpi", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\forward.png", "mouse_button_forward", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\back.png", "mouse_button_back", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\g7.png", "mouse_button_g7", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\g8.png", "mouse_button_g8", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\g9.png", "mouse_button_g9", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\scroll_left.png", "mouse_button_sl", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\scroll_right.png", "mouse_button_sr", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\scroll_down.png", "mouse_scroll_down", visible=False)
            self.add_overlay_image("assets\\mouse\\g502\\pressed\\scroll_up.png", "mouse_scroll_up", visible=False)
        # Check is the current mouse is the Cyro
        elif settings["mouse"] == "cyro":
            # If so, Create the Cyro Overlay
            self.add_overlay_image("assets\\mouse\\cyro\\base.png", "mouse_base")
            self.add_overlay_image("assets\\mouse\\cyro\\stick\\cap.png", "mouse_thumbstick_cap", 533, 270)
            self.add_overlay_image("assets\\mouse\\cyro\\stick\\pressed.png", "mouse_button_22", 533, 270, visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\1.png", "mouse_button_1", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\2.png", "mouse_button_2", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\3.png", "mouse_button_3", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\4.png", "mouse_button_4", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\5.png", "mouse_button_5", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\6.png", "mouse_button_6", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\7.png", "mouse_button_7", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\8.png", "mouse_button_8", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\9.png", "mouse_button_9", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\10.png", "mouse_button_10", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\11.png", "mouse_button_11", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\12.png", "mouse_button_12", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\14.png", "mouse_button_14", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\15.png", "mouse_button_15", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\16.png", "mouse_button_16", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\17.png", "mouse_button_17", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\20.png", "mouse_button_20", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\28.png", "mouse_button_28", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\29.png", "mouse_button_29", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\30.png", "mouse_button_30", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\31.png", "mouse_button_31", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\scroll_down.png", "mouse_scroll_down", visible=False)
            self.add_overlay_image("assets\\mouse\\cyro\\pressed\\scroll_up.png", "mouse_scroll_up", visible=False)
            self.add_overlay_image(f"assets\\mouse\\cyro\\edit_numbers\\base.png", "cyro_edit_base", visible=False)
            
        #add the mouse movement indicator to its default position
        self.add_overlay_image("assets\\mouse\\movement_indicator.png", "movement_indicator", 639, 381)


    def create_azeron_overlay(self):
        # Create the mouse overlay
        # Add all the base images
        self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\base.png", "azeron_base")
        self.add_overlay_image("assets\\azeron\\stick\\cap.png", "thumbstick_cap", 394, 323)
        self.add_overlay_image("assets\\azeron\\stick\\pressed.png", "azeron_button_23", 394, 323, visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\1.png", "azeron_button_1", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\2.png", "azeron_button_2", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\3.png", "azeron_button_3", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\4.png", "azeron_button_4", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\5.png", "azeron_button_5", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\6.png", "azeron_button_6", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\7.png", "azeron_button_7", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\8.png", "azeron_button_8", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\9.png", "azeron_button_9", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\10.png", "azeron_button_10", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\11.png", "azeron_button_11", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\12.png", "azeron_button_12", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\14.png", "azeron_button_14", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\15.png", "azeron_button_15", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\16.png", "azeron_button_16", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\17.png", "azeron_button_17", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\19.png", "azeron_button_19", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\22.png", "azeron_button_22", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\28.png", "azeron_button_28", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\29.png", "azeron_button_29", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\30.png", "azeron_button_30", visible=False)
        self.add_overlay_image("assets\\azeron\\pressed\\31.png", "azeron_button_31", visible=False)
        self.add_overlay_image(f"assets\\azeron\\edit_numbers\\base.png", "azeron_edit_base", visible=False)


        # Check if the selected model is the cyborg2
        if settings["model"] == "cyborg2":
            # If so, add the cyborg2 images
            self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\cyborg.png", "azeron_cyborg")
            self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\cyborg2.png", "azeron_cyborg2")
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg2\\20.png", "azeron_button_20", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg2\\41.png", "azeron_button_41", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\13.png", "azeron_button_13", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\18.png", "azeron_button_18", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\36.png", "azeron_button_36", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\37.png", "azeron_button_37", visible=False)
            self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\38.png", "azeron_button_38", visible=False)
            self.add_overlay_image(f"assets\\azeron\\edit_numbers\\cyborg.png", "azeron_edit_cyborg", visible=False)
            self.add_overlay_image(f"assets\\azeron\\edit_numbers\\cyborg2.png", "azeron_edit_cyborg2", visible=False)
        else:
            # If not, add the classic 20 image
            self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\classic_20.png", "azeron_classic_20")
            self.add_overlay_image("assets\\azeron\\pressed\\20.png", "azeron_button_20", visible=False)
            self.add_overlay_image(f"assets\\azeron\\edit_numbers\\classic_20.png", "azeron_edit_classic_20", visible=False)
            # Check if the selected model is the classic
            if settings["model"] == "classic":
                # If so, add the classic images
                self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\classic.png", "azeron_classic")
                self.add_overlay_image("assets\\azeron\\pressed\\classic\\13.png", "azeron_button_13", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\classic\\18.png", "azeron_button_18", visible=False)
                self.add_overlay_image(f"assets\\azeron\\edit_numbers\\classic.png", "azeron_edit_classic", visible=False)
            # Check if the selected model is the cyborg
            elif settings["model"] == "cyborg":
                # If so, add the cyborg images
                self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\cyborg.png", "azeron_cyborg")
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\13.png", "azeron_button_13", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\18.png", "azeron_button_18", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\36.png", "azeron_button_36", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\37.png", "azeron_button_37", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\38.png", "azeron_button_38", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\20.png", "azeron_button_20", visible=False)
                self.add_overlay_image(f"assets\\azeron\\edit_numbers\\cyborg.png", "azeron_edit_cyborg", visible=False)


    def add_overlay_image(self, image_path:str, key:str, x:int=0, y:int=0, visible:bool=True):
        # Overlay an image on the main window
        # Get the image from the path and convery it to the proper format
        overlay_photo = ImageTk.PhotoImage(Image.open(image_path)) 
        # Place the image at the specified coordinated and save the image id
        image_id = self.canvas.create_image(x, y, anchor="nw", image=overlay_photo)
        # Save the image id to a dictionary so it can be modified in the future, also to prevent the garbage collector from deleting it
        self.images[key] = [overlay_photo, image_id]
        # Check if the overlayed image is meant to be visible
        if not visible:
            # If not, make it invisible
            self.set_image_visibility(image_id, False)


    def set_image_visibility(self, key:str, visibility:bool):
        # Check if the provided key is an int (int:image object, str:dictionary key)
        if not isinstance(key, int):
            if key not in self.images.keys():
                return
            # If not get the image object from the dictionary
            key = int(self.images[key][1])

        # Check if the image is meant to be visible
        if visibility:
            # If so, set the images state to be visible
            self.canvas.itemconfigure(key, state='normal')
        else:
            # If not, set the images state to be invisible
            self.canvas.itemconfigure(key, state='hidden')


    def move_image(self, key:str, x:int, y:int):
        # Move an overlayed image
        if key not in self.images:
            return
        # Move the image
        self.canvas.coords(self.images[key][1], x, y)
        # Check if the moved image is the azeron thumbstick cap
        if key == "thumbstick_cap":
            # If so, move the thumbstick button with it
            self.canvas.coords(self.images["azeron_button_23"][1], x, y)
        # Check if the moved image is the mouse thumbstick cap
        if key == "mouse_thumbstick_cap":
            # If so, move the thumbstick button with it
            self.canvas.coords(self.images["mouse_button_22"][1], x, y)



if __name__ == "__main__":
    # Create threads for input handling and scroll wheel listener
    main_thread = Thread(target=main_input_loop, daemon=True)
    scroll_wheel_thread = Thread(target=scroll_wheel_listener, daemon=True)

    # Load settings from the JSON configuration file
    with open("settings.json", "r") as f:
        settings = json_load(f)

    # Load the active profile 
    load_profile(settings["loaded_profile"])

    # Get the current mouse position
    mouse_pos = get_mouse_pos()

    # Initialize the main Tkinter window
    root = tk.Tk()
    icon_photo = ImageTk.PhotoImage(Image.open("assets\\icon\\icon.png"))  # Load the application icon and convert to a format Tkinter can use

    # Set the window icon
    root.iconphoto(False, icon_photo)
    app = AzeronOverlayMainWindow(root)  # Create the main application window

    # Start the input handling and scroll wheel listener threads
    scroll_wheel_thread.start()
    main_thread.start()

    # Start the Tkinter event loop
    root.mainloop()
