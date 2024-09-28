from ctypes import wintypes as ctypes_wintypes, WinDLL as ctypes_WinDLL, Structure as ctypes_Structure, c_ubyte as ctypes_cubyte, c_long as ctypes_clong, c_short as ctypes_cshort, byref as ctypes_byref
from pynput.mouse import Listener as MouseListener
from threading import Thread
from copy import deepcopy
from time import sleep, time
from math import radians as math_radians, cos as math_cos, sin as math_sin, atan2 as math_atan2, sqrt as math_sqrt, degrees as math_degrees
import tkinter as tk
from PIL import Image, ImageTk
from json import dump as json_dump, load as json_load
from os import rename as os_rename, path as os_path, remove as os_remove, listdir as os_listdir

import button_map


user32 = ctypes_WinDLL('user32')
xinput1_4 = ctypes_WinDLL('XInput1_4.dll')


scroll_time = time()
mouse_move_time = time()

mouse_pos = (0, 0)
left_stick_pos = (0, 0)
right_stick_pos = (0, 0)

xinput_presses = ()
key_presses = ()

mouse_speed_indicator = None

pressed_movement_keys = {"azeron":(),"mouse":()}
movement_keys = {"azeron":{},"mouse":{}}

used_inputs = ()
used_xinputs = ()
used_sticks = {"left":False,"right":False}

profile = {}
settings = {}


empty_profile_template = {"azeron_keys": {"1": [], "2": [], "3": [], "4": [], "5": [], "6": [], "7": [], "8": [], "9": [], "10": [], "11": [], "12": [], "14": [], "15": [], "16": [], "17": [], "19": [], "20": [], "22": [], "23": [], "28": [], "29": [], "30": [], "31": [], "13": [], "18": [], "36": [], "37": [], "38": [], "41": []}, "stick": "xinput-l", "mouse_stick": "xinput-l", "mouse_keys": {"right": [2], "left": [1], "middle": [4], "forward": [6], "back": [5], "dpi": [], "1": [5], "2": [6], "3": [2], "4": [1], "5": [4], "6": [], "7": [], "8": [], "9": [], "10": [], "11": [], "12": [], "14": [], "15": [], "16": [], "17": [], "20": [], "22": [], "28": [], "29": [], "30": [], "31": [], "g7": [], "g8": [], "g9": [], "sl": [], "sr": []}}


class XINPUT_GAMEPAD(ctypes_Structure):
    _fields_ = [
        ("wButtons", ctypes_wintypes.WORD),
        ("bLeftTrigger", ctypes_cubyte),
        ("bRightTrigger", ctypes_cubyte),
        ("sThumbLX", ctypes_cshort),
        ("sThumbLY", ctypes_cshort),
        ("sThumbRX", ctypes_cshort),
        ("sThumbRY", ctypes_cshort)
    ]

class XINPUT_STATE(ctypes_Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes_wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD)
    ]
    
class POINT(ctypes_Structure):
    _fields_ = [("x", ctypes_clong), 
                ("y", ctypes_clong)]

def get_xinput_state(controller_index:int=0):
    state = XINPUT_STATE()
    if xinput1_4.XInputGetState(controller_index, ctypes_byref(state)) != 0:
        return None
    return state

def get_key_from_value(dictionary:dict, value:str):
    for key, val in dictionary.items():
        if val == value:
            return key
    return value


def get_key_presses(all=False):
    if all:
        return tuple(keycode for keycode in button_map.keyboard.keys() if user32.GetAsyncKeyState(keycode) & 0x8000)
    return tuple(keycode for keycode in used_inputs if user32.GetAsyncKeyState(keycode) & 0x8000)


def get_pressed_xinputs(all=False):
    gamepad = get_xinput_state()
    if gamepad == None:
        return ()
    gamepad = gamepad.Gamepad

    pressed_buttons = []
    for key, value in button_map.controller.items():
        if value not in used_xinputs and not all:
            continue
        if value == "XI.lt":
            if gamepad.bLeftTrigger > 0:
                pressed_buttons.append(value)
        elif value == "XI.rt":
            if gamepad.bRightTrigger > 0:
                pressed_buttons.append(value)
        elif gamepad.wButtons & key:
            pressed_buttons.append(value)

    return tuple(pressed_buttons)


def get_mouse_pos():
    pt = POINT()
    if user32.GetCursorPos(ctypes_byref(pt)):
        return (pt.x, pt.y)
    return (0, 0)


def get_thumbstick_pos(right=False):
    state = get_xinput_state()
    if state == None:  
        return (0, 0)
    if right:
        return (0 if -300<state.Gamepad.sThumbRX<300 else state.Gamepad.sThumbRX, 0 if -300<state.Gamepad.sThumbRY<300 else state.Gamepad.sThumbRY)
    return (0 if -300<state.Gamepad.sThumbLX<300 else state.Gamepad.sThumbLX, 0 if -300<state.Gamepad.sThumbLY<300 else state.Gamepad.sThumbLY)
        
        

def load_profile(profile_json:str):
    global profile, used_inputs, used_xinputs, movement_keys
    if not os_path.exists(profile_json):
        profiles = [f for f in os_listdir("profiles") if f.endswith('.json')]
        if profiles == []:
            create_new_profile()
            return
        edit_settings("loaded_profile", f"profiles\\{profiles[0]}")
        return
    with open(profile_json, "r") as f:
        profile = json_load(f)
    
        
    used_inputs_list = []
    used_xinputs_list = []
    for key, values in profile["azeron_keys"].items():
        if settings["model"] not in ["cyborg2"] and key in ["41"]:
            continue
        if settings["model"] not in ["cyborg", "cyborg2"] and key in ["36", "37", "38"]:
            continue
        if settings["model"] not in ["cyborg", "cyborg2", "classic"] and key in ["13", "18"]:
            continue
        for item in values:
            if type(item) == str:
                used_xinputs_list.append(item)
            else:
                used_inputs_list.append(item)
    for key, values in profile["mouse_keys"].items():
        if settings["mouse"] != "cyro" and key in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14", "15", "16", "17", "20", "22", "28", "29", "30", "31"]:
            continue
        if settings["mouse"] not in ["g403", "g502"] and key in ["right", "left", "middle", "forward", "back", "dpi"]:
            continue
        if settings["mouse"] != "g502" and key in ["g7", "g8", "g9", "sl", "sr"]:
            continue

        for item in values:
            if type(item) == str:
                used_xinputs_list.append(item)
            else:
                used_inputs_list.append(item)
    if type(profile["stick"]) != str:
        movement_keys["azeron"]["forward"], movement_keys["azeron"]["left"], movement_keys["azeron"]["back"], movement_keys["azeron"]["right"] = [x for x in profile["stick"]]
        for item in profile["stick"]:
            used_inputs_list.append(item)
    if type(profile["mouse_stick"]) != str:
        movement_keys["mouse"]["forward"], movement_keys["mouse"]["left"], movement_keys["mouse"]["back"], movement_keys["mouse"]["right"] = [x for x in profile["mouse_stick"]]
        for item in profile["mouse_stick"]:
            used_inputs_list.append(item)
    used_inputs = tuple(used_inputs_list)
    used_xinputs = tuple(used_xinputs_list)
    set_used_thumbsticks()


def set_used_thumbsticks():
    global used_sticks
    if profile["stick"] == "xinput-l" or (settings["mouse"] == "cyro" and profile["mouse_stick"] == "xinput-l"):
        used_sticks["left"]=True
    else:
        used_sticks["left"]=False

    if profile["stick"] == "xinput-r" or (settings["mouse"] == "cyro" and profile["mouse_stick"] == "xinput-r"):
        used_sticks["right"]=True
    else:
        used_sticks["right"]=False


def create_new_profile():
    file_path = f"profiles\\new-profile.json"
    i = 1
    while os_path.exists(file_path):
        file_path = f"profiles\\new-profile{i}.json"
        i += 1

    with open(file_path, "w") as f:
        json_dump(empty_profile_template, f)
    edit_settings("loaded_profile", file_path)


def edit_settings(key:str, value:str):
    global settings
    settings[key] = value
    with open("settings.json", "w") as f:
        json_dump(settings, f)
    if key == "loaded_profile":
        load_profile(value)
    if key == "mouse":
        set_used_thumbsticks()


def save_profile(profile:dict):
    with open(f"{settings["loaded_profile"]}", "w") as f:
        json_dump(profile, f)
    load_profile(settings["loaded_profile"])


def on_scroll(x:int, y:int, dx:int, dy:int):
    global scroll_time
    scroll_time = time()

    if dy == 0:
        pass
    elif dy>0: #On Scroll Up
        app.set_image_visibility(f"mouse_scroll_down", False)
        app.set_image_visibility(f"mouse_scroll_up", True)
    else:    #On Scroll Down
        app.set_image_visibility(f"mouse_scroll_up", False)
        app.set_image_visibility(f"mouse_scroll_down", True)


def input_handler(input:int|str, on:bool):
    for key, values in profile["azeron_keys"].items():
        if input in values:
            app.set_image_visibility(f"azeron_button_{key}", on)

    for key, values in profile["mouse_keys"].items():
        if input in values:
            app.set_image_visibility(f"mouse_button_{key}", on)


def wasd_handler(new_pressed_movement_keys:tuple, thumbstick_type="azeron"):
    global pressed_movement_keys
    if movement_keys[thumbstick_type]["forward"] in new_pressed_movement_keys and movement_keys[thumbstick_type]["back"] in new_pressed_movement_keys:
        y = 0
    elif movement_keys[thumbstick_type]["forward"] in new_pressed_movement_keys:
        y = 1
    elif movement_keys[thumbstick_type]["back"] in new_pressed_movement_keys:
        y = -1
    else:
        y = 0
    
    if movement_keys[thumbstick_type]["right"] in new_pressed_movement_keys and movement_keys[thumbstick_type]["left"] in new_pressed_movement_keys:
        x = 0
    elif movement_keys[thumbstick_type]["right"] in new_pressed_movement_keys:
        x = 1
    elif movement_keys[thumbstick_type]["left"] in new_pressed_movement_keys:
        x = -1
    else:
        x = 0
    
    #wasq [87, 65, 83, 81]
    if thumbstick_type == "azeron":
        #(394, 323)
        if (x, y) == (0, 0): # not moving
            app.move_image("thumbstick_cap", 394, 323) #0, 0
        if (x, y) == (0, 1): # forward
            app.move_image("thumbstick_cap", 394, 300) #0, -23
        if (x, y) == (1, 1): # forward right 
            app.move_image("thumbstick_cap", 410, 307) #+16, -16
        if (x, y) == (-1, 1): # forward left 
            app.move_image("thumbstick_cap", 378, 307) #-16, -16
        if (x, y) == (1, 0): # right
            app.move_image("thumbstick_cap", 417, 323) #23, 0
        if (x, y) == (-1, 0): # left
            app.move_image("thumbstick_cap", 371, 323) #-23, 0
        if (x, y) == (1, -1): # back right 
            app.move_image("thumbstick_cap", 410, 339) #+16, +16
        if (x, y) == (-1, -1): # back left 
            app.move_image("thumbstick_cap", 378, 339) #-16, +16
        if (x, y) == (0, -1): # back
            app.move_image("thumbstick_cap", 394, 346) #0, +23
    else:
        #(533, 270)
        if (x, y) == (0, 0): # not moving
            app.move_image("mouse_thumbstick_cap", 533, 270) #0, 0
        if (x, y) == (0, 1): # forward
            app.move_image("mouse_thumbstick_cap", 533, 254) #0, -16
        if (x, y) == (1, 1): # forward right 
            app.move_image("mouse_thumbstick_cap", 544.5, 258.5) #+11.5, -11.5
        if (x, y) == (-1, 1): # forward left 
            app.move_image("mouse_thumbstick_cap", 521.5, 258.5) #-11.5, -11.5
        if (x, y) == (1, 0): # right
            app.move_image("mouse_thumbstick_cap", 549, 270) #+16, 0
        if (x, y) == (-1, 0): # left
            app.move_image("mouse_thumbstick_cap", 517, 270) #-16, 0
        if (x, y) == (1, -1): # back right 
            app.move_image("mouse_thumbstick_cap", 544.5, 281.5) #+11.5, +11.5
        if (x, y) == (-1, -1): # back left 
            app.move_image("mouse_thumbstick_cap", 521.5, 281.5) #-11.5, +11.5
        if (x, y) == (0, -1): # back
            app.move_image("mouse_thumbstick_cap", 533, 286) #0, +16
    pressed_movement_keys[thumbstick_type] = new_pressed_movement_keys


i = 0
def main_input_loop():
    global i, mouse_speed_indicator, xinput_presses, key_presses, mouse_pos, left_stick_pos, right_stick_pos, mouse_move_time
    while True:
        i += 1
        sleep(0.01)

        current_time = time()

        new_xinput_presses = get_pressed_xinputs()
        for button in tuple(set(new_xinput_presses)-set(xinput_presses)): #on xinput press
            input_handler(button, True)
        for button in tuple(set(xinput_presses)-set(new_xinput_presses)): #on xinput release
            input_handler(button, False)

        xinput_presses = tuple(new_xinput_presses)

        
        new_key_presses = get_key_presses()
        for key in tuple(set(new_key_presses)-set(key_presses)): #on keyboard press
            input_handler(key, True)
        for key in tuple(set(key_presses)-set(new_key_presses)): #on keyboard release
            input_handler(key, False)
            
        key_presses = tuple(new_key_presses)


        if used_sticks["left"]:
            new_left_stick_pos = get_thumbstick_pos()
            if new_left_stick_pos != left_stick_pos:
                if profile["stick"] == "xinput-l":
                    app.move_image("thumbstick_cap", 394+int(((new_left_stick_pos[0] - -32767) / (32767 - -32767)) * (23 - -23) + -23), 323-int(((new_left_stick_pos[1] - -32767) / (32767 - -32767)) * (23 - -23) + -23))

                if profile["mouse_stick"] == "xinput-l" and settings["mouse"] == "cyro":
                    app.move_image("mouse_thumbstick_cap", 533+int(((new_left_stick_pos[0] - -32767) / (32767 - -32767)) * (17 - -17) + -17), 270-int(((new_left_stick_pos[1] - -32767) / (32767 - -32767)) * (17 - -17) + -17))
                left_stick_pos = tuple(new_left_stick_pos)
                

        if used_sticks["right"]:
            new_right_stick_pos = get_thumbstick_pos(right=True)
            if new_right_stick_pos != right_stick_pos:
                if profile["stick"] == "xinput-r":
                    app.move_image("thumbstick_cap", 394+int(((new_right_stick_pos[0] - -32767) / (32767 - -32767)) * (23 - -23) + -23), 323-int(((new_right_stick_pos[1] - -32767) / (32767 - -32767)) * (23 - -23) + -23))

                if profile["mouse_stick"] == "xinput-r" and settings["mouse"] == "cyro":
                    app.move_image("mouse_thumbstick_cap", 533+int(((new_right_stick_pos[0] - -32767) / (32767 - -32767)) * (17 - -17) + -17), 270-int(((new_right_stick_pos[1] - -32767) / (32767 - -32767)) * (17 - -17) + -17))
                right_stick_pos = tuple(new_right_stick_pos)

        if type(profile["stick"]) == list:
            new_pressed_movement_keys = tuple(set(key_presses)&set(movement_keys["azeron"].values()))
            if new_pressed_movement_keys != pressed_movement_keys["azeron"]:
                wasd_handler(new_pressed_movement_keys)

        if (type(profile["mouse_stick"]) == list and settings["mouse"] == "cyro"):
            new_pressed_movement_keys = tuple(set(key_presses)&set(movement_keys["mouse"].values()))
            if new_pressed_movement_keys != pressed_movement_keys["mouse"]:
                wasd_handler(new_pressed_movement_keys, thumbstick_type="mouse")


        if i % 5 == 0:
            new_mouse_pos = get_mouse_pos()
            if mouse_pos != new_mouse_pos:
                speed = math_sqrt((new_mouse_pos[0]-mouse_pos[0])**2 + (new_mouse_pos[1]-mouse_pos[1])**2) / max((current_time-mouse_move_time), 0.00001)
                direction = math_degrees(math_atan2((new_mouse_pos[1]-mouse_pos[1]), (new_mouse_pos[0]-mouse_pos[0])))
                if direction < 0:
                    direction += 360

                if speed > 15000:
                    speed = 15000
                speed = int(((speed - 0) / (15000 - 0)) * (72 - 0) + 0)

                angle_rad = math_radians(direction)
                #radius = 72
                #center = (639, 381)
                position = (int(639 + 72*math_cos(angle_rad)), int(381 + 72*math_sin(angle_rad)))

                app.move_image("movement_indicator", position[0], position[1])
                if mouse_speed_indicator != None:
                    app.canvas.delete(mouse_speed_indicator)
                    mouse_speed_indicator = None
                
                mouse_speed_indicator = app.canvas.create_line(653, 395, (653 + speed * math_cos(angle_rad)), (395 + speed * math_sin(angle_rad)), fill='white', width=5)

                mouse_pos = tuple(new_mouse_pos)
                mouse_move_time = current_time
            else:
                app.move_image("movement_indicator", 639, 381)
                if mouse_speed_indicator != None:
                    app.canvas.delete(mouse_speed_indicator)
                    mouse_speed_indicator = None
            
            if (current_time - scroll_time) > 0.05:
                app.set_image_visibility(f"mouse_scroll_up", False)
                app.set_image_visibility(f"mouse_scroll_down", False)



scroll_wheel_listener = MouseListener(on_scroll=on_scroll)
main_thread = Thread(target=main_input_loop, daemon=True)



with open("settings.json", "r") as f:
    settings = json_load(f)

load_profile(settings["loaded_profile"])

mouse_pos = get_mouse_pos()



class ImageOverlayWindow:
    def __init__(self, root):
        self.button_edit_items = []
        self.set_button_labels = []
        self.thumbstick_wasd_buttons = []
        self.thumbstick_xinput_buttons = []
        self.images = {}
        self.new_profile = {}
        self.root = root
        self.root.title("AzBoard")
        self.root.resizable(False, False)

        # Create a menu bar
        self.menu_bar = tk.Menu(root)
        root.config(menu=self.menu_bar)

        self.profiles_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_command(label="Settings", command=self.open_settings_window)
        self.menu_bar.add_cascade(label="Profiles", menu=self.profiles_menu)
        self.menu_bar.add_cascade(label="active profile", menu=None, command=None)


        self.canvas = tk.Canvas(self.root, width=800, height=500, bg="#00ff00", borderwidth=0, highlightthickness=0)
        self.canvas.pack()

        self.update_profiles_menu()

        self.create_mouse_overlay()
        self.create_azeron_overlay()



    def open_settings_window(self):

        settings_window = tk.Toplevel(root)
        settings_window.title("Settings")
        settings_window.geometry("300x200")
        settings_window.grab_set()
        settings_window.resizable(False, False)
        
        tk.Label(settings_window, text="Model:").pack(anchor="w", padx=10, pady=5)
        model_var = tk.StringVar(value=settings["model"])
        model_menu = tk.OptionMenu(settings_window, model_var, "classic", "compact", "cyborg", "cyborg2")
        model_menu.pack(anchor="w", padx=15)
        
        tk.Label(settings_window, text="Color:").pack(anchor="w", padx=10, pady=5)
        color_var = tk.StringVar(value=settings["color"])
        color_menu = tk.OptionMenu(settings_window, color_var, "black", "blue", "purple", "red", "baby-blue")
        color_menu.pack(anchor="w", padx=15)
        
        tk.Label(settings_window, text="Mouse:").pack(anchor="w", padx=10, pady=5)
        mouse_var = tk.StringVar(value=settings["mouse"])
        mouse_menu = tk.OptionMenu(settings_window, mouse_var, "g403", "g502", "cyro")
        mouse_menu.pack(anchor="w", padx=15)
        
        def delete_window():
            global settings
            new_settings = deepcopy(settings)
            new_settings["model"] = model_var.get()
            new_settings["color"] = color_var.get()
            new_settings["mouse"] = mouse_var.get()
            if new_settings != settings:
                settings = deepcopy(new_settings)
                with open("settings.json", "w") as f:
                    json_dump(new_settings, f)

                self.clear_images()
                self.create_azeron_overlay()
                self.create_mouse_overlay()
                set_used_thumbsticks()
                load_profile(settings["loaded_profile"])

            settings_window.destroy()
        settings_window.protocol("WM_DELETE_WINDOW", delete_window)


    def button_edit_stuff(self, button:str, button_type:str):
        for item in self.button_edit_items:
            try:
                item.destroy()
            except:
                pass
        self.button_edit_items = []
        for item in self.thumbstick_wasd_buttons:
            try:
                item.destroy()
            except:
                pass
        self.thumbstick_wasd_buttons = []
        for item in self.thumbstick_xinput_buttons:
            try:
                item.destroy()
            except:
                pass
        self.thumbstick_xinput_buttons = []
        for item in self.set_button_labels:
            try:
                item.destroy()
            except:
                pass
        self.set_button_labels = []
        if button == "sl":
            text = f"{button_type}: scroll left"
        elif button == "sr":
            text = f"{button_type}: scroll right"
        else:
            text = f"{button_type}: {button}"
        label = tk.Label(self.edit_profile_window, text=text)
        label.place(x=1, y=282)
        self.button_edit_items.append(label)


        def update_item_button(key_type:str, key_name:str, old_name, listbox_index):
            key = ()
            label = tk.Label(self.edit_profile_window, text="Press Something...", font=("Arial", 27))
            label.place(x=150, y=402)
            self.set_button_labels.append(label)
            while key == ():
                sleep(0.001)
                key = get_key_presses(all=True)
                if key == ():
                    key = get_pressed_xinputs(all=True)
            key = key[0]
            for item in self.set_button_labels:
                item.destroy()
            self.set_button_labels = []
            if old_name == "empty":
                self.new_profile[key_type][key_name].append(key)
            else:
                self.new_profile[key_type][key_name] = [key if x == old_name else x for x in self.new_profile[key_type][key_name]]
            listbox.delete(listbox_index)
            if type(key) == str:
                pass
            else:
                key = button_map.keyboard[key]
            listbox.insert(listbox_index, key) 
            self.button_edit_items.remove(self.record_button)
            self.record_button.destroy()
            self.delete_button.destroy()

        
        def delete_item_button(index, key_type, key_name, selected_item):
            listbox.delete(index)
            if selected_item != "empty":
                self.new_profile[key_type][key_name].remove(get_key_from_value(button_map.keyboard, selected_item))
            self.button_edit_items.remove(self.delete_button)
            self.record_button.destroy()
            self.delete_button.destroy()
        

        def on_select(event):
            listbox = event.widget
            index = listbox.curselection()
            if not index:
                return
            
            selected_item = listbox.get(index)
            key_type, key_name = listbox._name.split("|")
            #print(f"Type: {key_type} Key: {key_name} Selected: {selected_item}")

            self.record_button = tk.Button(self.edit_profile_window, text="Set Key", width=10, height=5, command=lambda: Thread(target=update_item_button, args=(key_type, key_name, get_key_from_value(button_map.keyboard, selected_item), index)).start())
            self.record_button.place(x=150, y=282)
            self.button_edit_items.append(self.record_button)

            self.delete_button = tk.Button(self.edit_profile_window, text="Delete", width=16, command=lambda: delete_item_button(index, key_type, key_name, selected_item))
            self.delete_button.place(x=1, y=470)
            self.button_edit_items.append(self.delete_button)


        def change_movement_buttons(index, old_keycode, button):
            key = ()
            label = tk.Label(self.edit_profile_window, text="Press a key...", font=("Arial", 27))
            label.place(x=150, y=402)
            self.set_button_labels.append(label)
            while key == ():
                sleep(0.001)
                key = get_key_presses(all=True)
            key = key[0]
            for item in self.set_button_labels:
                item.destroy()
            self.set_button_labels = []
            if key == old_keycode:
                return
            self.new_profile[self.thumbstick_key][index] = key
            button.config(text=button_map.keyboard[key])


        def change_thumbstick():
            if self.active_thumbstick.get() == self.new_profile[self.thumbstick_key]:
                return
            self.new_profile[self.thumbstick_key] = self.active_thumbstick.get()


        def toggle_thumbstick():
            if self.stick_type.get() == "Keyboard":
                if type(self.new_profile[self.thumbstick_key]) == list:
                    return
                for item in self.thumbstick_xinput_buttons:
                    try:
                        item.destroy()
                    except:
                        pass
                self.thumbstick_xinput_buttons = []
                self.new_profile[self.thumbstick_key] = [87, 65, 83, 68]

                label = tk.Label(self.edit_profile_window, text="Up:")
                label.place(x=7, y=360)
                self.thumbstick_wasd_buttons.append(label)
                up_button = tk.Button(self.edit_profile_window, text="KB.w", command=lambda: Thread(target=change_movement_buttons, args=(0, self.new_profile[self.thumbstick_key][0], up_button)).start())
                up_button.place(x=46, y=360)
                self.thumbstick_wasd_buttons.append(up_button)

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
                if type(self.new_profile[self.thumbstick_key]) == str:
                    return
                for item in self.thumbstick_wasd_buttons:
                    try:
                        item.destroy()
                    except:
                        pass
                self.thumbstick_wasd_buttons = []
                self.new_profile[self.thumbstick_key] = "xinput-l"
                self.active_thumbstick = tk.StringVar(value="xinput-l")
                left_stick_button =  tk.Radiobutton(self.edit_profile_window, text="Left",  variable=self.active_thumbstick, value="xinput-l", command=change_thumbstick)
                right_stick_button = tk.Radiobutton(self.edit_profile_window, text="Right", variable=self.active_thumbstick, value="xinput-r", command=change_thumbstick)
                self.edit_profile_canvas.create_window(7, 380, anchor=tk.NW, window=left_stick_button)
                self.edit_profile_canvas.create_window(7, 400, anchor=tk.NW, window=right_stick_button)
                self.thumbstick_xinput_buttons.append(left_stick_button)
                self.thumbstick_xinput_buttons.append(right_stick_button)
            

        if button == "thumbstick":
            if button_type == "keypad":
                self.thumbstick_key = "stick"
            else:
                self.thumbstick_key = "mouse_stick"
            
            label = tk.Label(self.edit_profile_window, text="Select Input Mode:")
            label.place(x=1, y=300)
            self.button_edit_items.append(label)

            if type(self.new_profile[self.thumbstick_key]) == str:
                self.stick_type = tk.StringVar(value="XInput")
                self.active_thumbstick = tk.StringVar(value=self.new_profile[self.thumbstick_key])
                left_stick_button =  tk.Radiobutton(self.edit_profile_window, text="Left",  variable=self.active_thumbstick, value="xinput-l",  command=change_thumbstick)
                right_stick_button = tk.Radiobutton(self.edit_profile_window, text="Right", variable=self.active_thumbstick, value="xinput-r",  command=change_thumbstick)
                self.edit_profile_canvas.create_window(7, 380, anchor=tk.NW, window=left_stick_button)
                self.edit_profile_canvas.create_window(7, 400, anchor=tk.NW, window=right_stick_button)
                self.thumbstick_xinput_buttons.append(left_stick_button)
                self.thumbstick_xinput_buttons.append(right_stick_button)
            else:
                self.stick_type = tk.StringVar(value="Keyboard")
                label = tk.Label(self.edit_profile_window, text="Up:")
                label.place(x=7, y=360)
                self.thumbstick_wasd_buttons.append(label)
                up_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][0]], command=lambda: Thread(target=change_movement_buttons, args=(0, self.new_profile[self.thumbstick_key][0], up_button)).start())
                up_button.place(x=46, y=360)
                self.thumbstick_wasd_buttons.append(up_button)

                label = tk.Label(self.edit_profile_window, text="Left:")
                label.place(x=7, y=390)
                self.thumbstick_wasd_buttons.append(label)
                left_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][1]], command=lambda: Thread(target=change_movement_buttons, args=(1, self.new_profile[self.thumbstick_key][1], left_button)).start())
                left_button.place(x=46, y=390)
                self.thumbstick_wasd_buttons.append(left_button)

                label = tk.Label(self.edit_profile_window, text="Down:")
                label.place(x=7, y=420)
                self.thumbstick_wasd_buttons.append(label)
                down_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][2]], command=lambda: Thread(target=change_movement_buttons, args=(2, self.new_profile[self.thumbstick_key][2], down_button)).start())
                down_button.place(x=46, y=420)
                self.thumbstick_wasd_buttons.append(down_button)

                label = tk.Label(self.edit_profile_window, text="Right:")
                label.place(x=7, y=450)
                self.thumbstick_wasd_buttons.append(label)
                right_button = tk.Button(self.edit_profile_window, text=button_map.keyboard[self.new_profile[self.thumbstick_key][3]], command=lambda: Thread(target=change_movement_buttons, args=(3, self.new_profile[self.thumbstick_key][3], right_button)).start())
                right_button.place(x=46, y=450)
                self.thumbstick_wasd_buttons.append(right_button)

            xinput_button = tk.Radiobutton(self.edit_profile_window, text="XInput", variable=self.stick_type,     value="XInput",   command=toggle_thumbstick)
            keyboard_button = tk.Radiobutton(self.edit_profile_window, text="Keyboard", variable=self.stick_type, value="Keyboard", command=toggle_thumbstick)
            self.edit_profile_canvas.create_window(1, 320, anchor=tk.NW, window=xinput_button)
            self.edit_profile_canvas.create_window(1, 340, anchor=tk.NW, window=keyboard_button)
            self.button_edit_items.append(xinput_button)
            self.button_edit_items.append(keyboard_button)


        else:
            if button_type == "mouse":
                key_type="mouse_keys"
            else:
                key_type="azeron_keys"
        
            listbox = tk.Listbox(self.edit_profile_window, name=f"{key_type}|{button}")
            for item in self.new_profile[key_type][button]:
                if item in button_map.keyboard.keys():
                    listbox.insert(tk.END, button_map.keyboard[item])
                else:
                    listbox.insert(tk.END, item)

            self.edit_profile_canvas.create_window(1, 302, anchor=tk.NW, window=listbox)
            listbox.bind("<<ListboxSelect>>", on_select)
            add_button = tk.Button(self.edit_profile_window, text="+", width=2, command=lambda: listbox.insert(tk.END, "empty"))
            add_button.place(x=100, y=282)
            self.button_edit_items.append(listbox)
            self.button_edit_items.append(add_button)


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

        profiles_submenu.add_command(label="new...", command=lambda: (create_new_profile(), self.update_profiles_menu())) #make new empty profile
        for profile_name in [f[:-5] for f in os_listdir("profiles") if f.endswith('.json')]:
            if profile_name == settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""):
                continue
            profiles_submenu.add_command(label=profile_name, command=lambda p=profile_name: (edit_settings("loaded_profile", f"profiles\\{p}.json"), self.update_profiles_menu()))

        # Add the profiles submenu with the current profile highlighted
        self.profiles_menu.add_cascade(label=f"{settings['loaded_profile'].replace('profiles\\', '').replace('.json', '')}", menu=profiles_submenu)

        # Add the Edit option
        self.profiles_menu.add_command(label="Edit", command=self.open_profile_edit_window)
        

        def delete_profile(profile_name):
            if not os_path.exists(profile_name):
                return
            os_remove(profile_name)
            edit_settings("loaded_profile", f"profiles\\{[f for f in os_listdir("profiles") if f.endswith('.json')][0]}")
            self.update_profiles_menu()
            
        if len([f for f in os_listdir("profiles") if f.endswith('.json')]) >= 2:
            delete_menu_1 = tk.Menu(self.profiles_menu, tearoff=0)
            self.profiles_menu.add_cascade(label="Delete", menu=delete_menu_1)
            delete_menu_2 = tk.Menu(self.profiles_menu, tearoff=0)
            delete_menu_1.add_cascade(label="you sure?", menu=delete_menu_2)
            delete_menu_2.add_command(label="yes", command=lambda:delete_profile(settings["loaded_profile"]))

        self.menu_bar.entryconfig(3, label=settings["loaded_profile"].replace("profiles\\", "").replace(".json", ""))



    def clear_images(self):
        for key, value in dict(self.images).items():
            self.canvas.delete(value[1])
            del self.images[key]



    def create_mouse_overlay(self):
        if settings["mouse"] == "g403":
            self.add_overlay_image("assets\\mouse\\g403\\base.png", "mouse_base")
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\left.png", "mouse_button_left", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\right.png", "mouse_button_right", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\middle.png", "mouse_button_middle", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\dpi.png", "mouse_button_dpi", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\forward.png", "mouse_button_forward", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\back.png", "mouse_button_back", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\scroll_down.png", "mouse_scroll_down", visible=False)
            self.add_overlay_image("assets\\mouse\\g403\\pressed\\scroll_up.png", "mouse_scroll_up", visible=False)
        elif settings["mouse"] == "g502":
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
        elif settings["mouse"] == "cyro":
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
            
            
        self.add_overlay_image("assets\\mouse\\movement_indicator.png", "movement_indicator", 639, 381)


    def create_azeron_overlay(self):
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


        
        if settings["model"] == "cyborg2":
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
            self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\classic_20.png", "azeron_classic_20")
            self.add_overlay_image("assets\\azeron\\pressed\\20.png", "azeron_button_20", visible=False)
            self.add_overlay_image(f"assets\\azeron\\edit_numbers\\classic_20.png", "azeron_edit_classic_20", visible=False)

            if settings["model"] == "classic":
                self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\classic.png", "azeron_classic")
                self.add_overlay_image("assets\\azeron\\pressed\\classic\\13.png", "azeron_button_13", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\classic\\18.png", "azeron_button_18", visible=False)
                self.add_overlay_image(f"assets\\azeron\\edit_numbers\\classic.png", "azeron_edit_classic", visible=False)
            elif settings["model"] == "cyborg":
                self.add_overlay_image(f"assets\\azeron\\colors\\{settings["color"]}\\cyborg.png", "azeron_cyborg")
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\13.png", "azeron_button_13", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\18.png", "azeron_button_18", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\36.png", "azeron_button_36", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\37.png", "azeron_button_37", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\cyborg\\38.png", "azeron_button_38", visible=False)
                self.add_overlay_image("assets\\azeron\\pressed\\20.png", "azeron_button_20", visible=False)
                self.add_overlay_image(f"assets\\azeron\\edit_numbers\\cyborg.png", "azeron_edit_cyborg", visible=False)


    def add_overlay_image(self, image_path, key, x=0, y=0, visible=True):
        overlay_photo = ImageTk.PhotoImage(Image.open(image_path))
        image_id = self.canvas.create_image(x, y, anchor="nw", image=overlay_photo)
        self.images[key] = [overlay_photo, image_id]
        if not visible:
            self.set_image_visibility(image_id, False)


    def set_image_visibility(self, key:str, visibility:bool):
        if type(key) != int:
            if key not in self.images.keys():
                return
            key = int(self.images[key][1])

        if visibility:
            self.canvas.itemconfigure(key, state='normal')
        else:
            self.canvas.itemconfigure(key, state='hidden')


    def move_image(self, key:str, x:int, y:int):
        if key not in self.images:
            return
        
        self.canvas.coords(self.images[key][1], x, y)
        if key == "thumbstick_cap":
            self.canvas.coords(self.images["azeron_button_23"][1], x, y)
        if key == "mouse_thumbstick_cap":
            self.canvas.coords(self.images["mouse_button_22"][1], x, y)



if __name__ == "__main__":
    root = tk.Tk()
    icon_image = Image.open("assets\\icon\\icon.png")
    icon_photo = ImageTk.PhotoImage(icon_image)

    root.iconphoto(False, icon_photo)
    app = ImageOverlayWindow(root)

    scroll_wheel_listener.start()
    main_thread.start()

    root.mainloop()