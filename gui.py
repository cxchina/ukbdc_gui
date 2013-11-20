#!/usr/bin/env python3
from tkinter import *
from tkinter.filedialog import *
from tkinter.messagebox import *
import sys
import xml.etree.ElementTree as ET
import hashlib

from ukbdc_lib.layout import *
from ukbdc_lib import UKBDC, USBError
from ukbdc_lib.mnemonics import mnemonics

from buttons import Buttons

def platform_windows():
	return sys.platform.startswith("win")

class KeyButton(Button):
	_fgcol    = "black"   # text color
	_inhfgcol = "#999999" # text color if inherited
	_prcol    = "red"     # press action label color
	_recol    = "blue"    # release action label color
	_nocol    = "#555555" # number label color
	_hibgcol  = "#90EE90" # background color if highlighted
	_ahibgcol = "#60FF60" # mouse-over background color if highlighted
	_labfont  = (None, 7, "normal") # label font
	# on windows, reset active highlighted color, because windows does not highlight
	if platform_windows():
		_ahibgcol = _hibgcol

	def __init__(self, master, number, command = lambda: False, *args, **kwargs):
		super(KeyButton, self).__init__(master, command = self._on_click, *args, **kwargs)
		self._ = {} # subwidgets
		self._mouse_over = False
		self._number = number
		self._command = command
		self._bgcol = self.cget("bg") # remember bg color for later use
		self._abgcol = self.cget("activebackground") # ... and mouse-over background color
		self.bind("<Leave>", self._on_leave)
		self.bind("<Enter>", self._on_enter)
		# make labels
		self._['l_no'] = Label(self, text = self.number,
				fg = self._nocol, bg = self._bgcol, font = self._labfont)
		self._['l_pr'] = Label(self, text = "",
				fg = self._prcol, bg = self._bgcol, font = self._labfont)
		self._['l_re'] = Label(self, text = "",
				fg = self._recol, bg = self._bgcol, font = self._labfont)
		# make sure clicking on labels works
		for label in self._.values():
			label.bind("<Button-1>", lambda x: self.invoke())
		self._layout_labels()
		for x in range(3):
			Grid.columnconfigure(self, x, weight = 1)
			Grid.rowconfigure(self, x, weight = 1)
		Grid.columnconfigure(self, 1, weight = 10)
		Grid.rowconfigure(self, 1, weight = 10)

	def _layout_labels(self):
		# windows quirk hack
		self._['l_no'].grid_forget()
		self._['l_pr'].grid_forget()
		self._['l_re'].grid_forget()
		self._['l_no'].grid(column = 0, row = 0, sticky = N+W)
		self._['l_pr'].grid(column = 0, row = 2, sticky = S+W)
		self._['l_re'].grid(column = 2, row = 2, sticky = S+E)

	def _on_enter(self, event):
		self._mouse_over = True
		# update labels to have the same background as button
		color = self.cget("activebackground")
		self._set_labels_color(color)

	def _on_leave(self, event):
		self._mouse_over = False
		# update labels to have the same background as button
		color = self.cget("background")
		self._set_labels_color(color)
		# windows hack
		if platform_windows():
			self._layout_labels()

	def _on_click(self):
		# run callback
		self._command(self)

	def _set_labels_color(self, color):
		for label in self._.values():
			label.config(bg = color)

	# returns label for an action (relative or absolute)
	def _generate_label(self, prefix, action):
		try:
			arg = str(action.arg)
		except ValueError:
			arg = ""
		if action.kind == Action.Rel:
			if action.arg >= 0:
				s = "+" + arg
			else:
				s = arg
			n = s
		elif action.kind == Action.Abs:
			n = arg
		else:
			n = ""
		if n == "":
			return ""
		else:
			return prefix + n

	def _update_press_label(self, action, inherited):
		self._['l_pr'].config(text = self._generate_label("↓", action))
		if inherited:
			self._['l_pr'].config(fg = self._inhfgcol)
		else:
			self._['l_pr'].config(fg = self._prcol)

	def _update_release_label(self, action, inherited):
		self._['l_re'].config(text = self._generate_label("↑", action))
		if inherited:
			self._['l_re'].config(fg = self._inhfgcol)
		else:
			self._['l_re'].config(fg = self._recol)

	# Public API starts here...

	@property
	def number(self):
		return self._number

	def highlight(self):
		self.config(activebackground = self._ahibgcol, bg = self._hibgcol)
		if self._mouse_over:
			self._set_labels_color(self._ahibgcol)
		else:
			self._set_labels_color(self._hibgcol)

	def dehighlight(self):
		self.config(activebackground = self._abgcol, bg = self._bgcol)
		if self._mouse_over:
			self._set_labels_color(self._abgcol)
		else:
			self._set_labels_color(self._bgcol)

	def set_keydef(self, kd):
		self.config(text = kd.nicename)
		if kd.inherited:
			self.config(fg = self._inhfgcol, relief = SUNKEN)
			self._['l_no'].config(fg = self._inhfgcol)
		else:
			self.config(fg = self._fgcol, bg = self._bgcol, relief = RAISED)
			self._['l_no'].config(fg = self._nocol)
		self._update_press_label(kd.press, kd.inherited)
		self._update_release_label(kd.release, kd.inherited)

class KeyboardFrame(Frame):
	# on_button_pressed will receive the button number
	# or Null if a button was deselected
	def __init__(self, master, on_button_pressed):
		super(KeyboardFrame, self).__init__(master)
		self._ = {}
		self._button_callback = on_button_pressed
		self._cur_button = None
		# initialize actual keyboard dimensions to (1, 1),
		# because we don't know the dimensions yet
		self.bind("<Button-1>", self._on_click_nothing)
		self.bind("<Configure>", self._on_change_size)
		self._['f_cont'] = Frame(self)

	# set keyboard containter size to a fixed ratio, and fill the frame with it
	def _on_change_size(self, event):
		ratio = float(self._bdefs.width) / self._bdefs.height
		myratio = float(self.winfo_width()) / self.winfo_height()
		if myratio > ratio:
			h = self.winfo_height()
			w = h * ratio
		else:
			w = self.winfo_width()
			h = w / ratio
		self._['f_cont'].place(
				anchor = CENTER,
				width = w, height = h,
				relx = 0.5, rely = 0.5)

	# triggered by one of the contained buttons
	# pass button press info to parent to decide what to do with it
	def _on_button_pressed(self, button):
		self._button_callback(button.number)

	def _on_click_nothing(self, event):
		if self._cur_button is not None:
			self._button_callback(None)

	def _get_btn_widget(self, no):
		return self._['b_%i' % no]

	# Public API starts here...

	def update_button(self, no, kd):
		b = self._get_btn_widget(no)
		b.set_keydef(kd)

	def get_current_btn(self):
		if self._cur_button is None:
			return None
		else:
			return self._cur_button.number

	def set_current_btn(self, no):
		if self._cur_button is not None:
			self._cur_button.dehighlight()
			self._cur_button = None
		if no is not None:
			self._cur_button = self._get_btn_widget(no)
			self._cur_button.highlight()

	# Goes to the next button. Maybe it shouldn't be here...
	def next_button(self):
		if self._cur_button is None:
			return
		nos = sorted(self._bdefs.keys())
		pos = nos.index(self._cur_button.number) + 1
		if pos >= len(nos):
			pos = 0
		self._on_button_pressed(self._get_btn_widget(nos[pos]))

	def setup_buttons(self, btns):
		self._bdefs = btns
		for no, button in btns.items():
			widget = KeyButton(self._['f_cont'], no, command = self._on_button_pressed)
			widget.grid(column = 0, row = 0, sticky = N+S+E+W)
			widget.place(
					relx = float(button.x) / btns.width,
					rely = float(button.y) / btns.height,
					relwidth = float(button.width) / btns.width,
					relheight = float(button.height) / btns.height
			)
			self._['b_%i' % no] = widget

# A decorator which switches off notifications before the function is called to prevent
# notifications in functions which set Tkinter variables
def no_notify(method):
	def _decorator(self, *args, **kwargs):
		old_should = self._should_notify
		self._should_notify = False
		method(self, *args, **kwargs)
		self._should_notify = old_should
	return _decorator

class ActionChooser(Frame):
	_action_types = {
			Action.NoAct: "none",
			Action.Rel  : "change layer by",
			Action.Abs  : "go to layer"
	}
	def __init__(self, master, on_change):
		super(ActionChooser, self).__init__(master)
		self._ = {}
		self._should_notify = False
		self._active = True
		self._on_change = on_change
		self._action_var = IntVar()
		self._action_var.trace("w", self._on_radio_changed)
		self._action_arg_var = StringVar()
		self._action_arg_var.set("0")
		self._action_arg_var.trace("w", self._on_action_arg_changed)
		vcmd = (master.register(self._validate_act), '%P')
		self._['e_action_arg'] = Entry(self, textvariable = self._action_arg_var,
				validate = "key", validatecommand = vcmd,
				width = 4, state = DISABLED)
		self._['e_action_arg'].var = self._action_arg_var
		self._['e_action_arg'].grid(column = 1, row = 1, rowspan = 2, padx = 8)
		for i, t in self._action_types.items():
			r = self._['r_' + str(i)] = Radiobutton(self, text = t, value = i, variable = self._action_var)
			r.grid(column = 0, row = i, sticky = W)
		self._should_notify = True

	def _validate_act(self, text):
		act = self._action_var.get()
		if len(text) == 0:
			return True
		elif act == Action.Rel and text == "-":
			return True
		elif act == Action.Abs and text == "-":
			return False
		else:
			try:
				n = int(text)
			except:
				return False
			if act == Action.Rel:
				return n >= -16 and n <= 16
			else:
				return n >= 0 and n <= 16

	# Whether the argument entry is complete (i. e. not "-" or empty)
	@property
	def _action_arg_complete(self):
		text = self._['e_action_arg'].var.get()
		try:
			n = int(text)
			return True
		except ValueError:
			return False

	def _on_radio_changed(self, *unused):
		no_notify = False
		entry = self._['e_action_arg']
		if self._action_var.get() == Action.NoAct:
			if not self._action_arg_complete:
				no_notify = True
				entry.var.set("0")
		if self._action_var.get() == Action.Abs:
			try:
				i = int(entry.var.get())
			except ValueError:
				i = 0
			if i <= 0:
				no_notify = True
				entry.var.set("0")
		self._update_action_arg_entry()
		# update focus only if the change was because of user, not by parent loading action definition
		if self._should_notify:
			entry.focus_set()
			entry.selection_range(0, END)
		if not no_notify:
			self._notify()

	def _on_action_arg_changed(self, *unused_args):
		if self._action_arg_complete:
			self._notify()

	def _update_action_arg_entry(self):
		if self._action_var.get() == Action.NoAct:
			self._['e_action_arg'].config(state = DISABLED)
		else:
			self._['e_action_arg'].config(state = NORMAL)

	def _notify(self):
		if self._should_notify:
			self._on_change()

	def config(self, *args, **kwargs):
		if 'state' in kwargs:
			if kwargs['state'] == DISABLED:
				self.active = False
			else:
				self.active = True
			del kwargs['state']
		super(ActionChooser, self).config(*args, **kwargs)

	# Public API starts here...

	@no_notify
	def update_action(self, action):
		self._action_var.set(action.kind)
		self._action_arg_var.set(str(action.arg))

	def get_action(self):
		act = Action(self._action_var.get(), int(self._action_arg_var.get()))
		return act

	@property
	def active(self):
		return _active

	@active.setter
	def active(self, act):
		if act:
			self._active = True
			for w in self._.values():
				w.config(state = NORMAL)
		else:
			self._active = False
			for w in self._.values():
				w.config(state = DISABLED)

class ScancodeEntry(Frame):
	_wrong_bgcolor = "#FF6D72"
	def __init__(self, master, on_change):
		super(ScancodeEntry, self).__init__(master)
		self._ = {}
		self._on_change = on_change
		self._active = True
		self._should_notify = False
		self._mnemonic_var = StringVar()
		self._mnemonic_var.set("")
		self._mnemonic_var.trace("w", self._on_mnemonic_changed)
		self._['e_mnemonic'] = Entry(self, textvariable = self._mnemonic_var)
		self._correct_bgcolor = self._['e_mnemonic'].cget("bg")
		self._['e_mnemonic'].bind("<FocusOut>", self._on_entry_tab)
		self._['e_mnemonic'].grid(column = 0, row = 0)
		self._['l_hints'] = Label(self)
		self._['l_hints'].grid(column = 1, row = 0)
		self._hints = []
		self._mnemonic = ""
		self._should_notify = True

	def _on_entry_tab(self, event):
		if len(self._hints) == 1 and self._mnemonic_var.get() != self._hints[0]:
			self._mnemonic_var.set(self._hints[0])
			self._['e_mnemonic'].icursor(END)
			self._['e_mnemonic'].focus_set()

	def _on_mnemonic_changed(self, *unused):
		if not self._mnemonic_correct:
			self._['e_mnemonic'].config(bg = self._wrong_bgcolor)
		else:
			self._['e_mnemonic'].config(bg = self._correct_bgcolor)
			self._mnemonic = self._mnemonic_var.get()
		if len(self._mnemonic_var.get()) == 0:
			self._hints = []
		else:
			self._hints = list(filter(
					lambda x: x.startswith(self._mnemonic_var.get()),
					mnemonics.values())
			)
		self._['l_hints'].config(text = " ".join(self._hints))
		if self._mnemonic_correct:
			self._notify()

	@property
	def _mnemonic_correct(self):
		text = self._mnemonic_var.get()
		if len(text) == 0:
			return True
		if text[0:2] == "0x":
			try:
				return 0 <= int(text, 16) <= 255
			except ValueError:
				return False
		else:
			valid_mnemonics = mnemonics.values()
			return text in valid_mnemonics

	def _notify(self):
		if self._should_notify:
			self._on_change()

	def config(self, *args, **kwargs):
		if 'state' in kwargs:
			if kwargs['state'] == DISABLED:
				self.active = False
			else:
				self.active = True
			del kwargs['state']
		super(ScancodeEntry, self).config(*args, **kwargs)

	# Public API starts here...

	@property
	def scancode(self):
		if self._mnemonic == "":
			return 0
		elif self._mnemonic.startswith("0x"):
			return int(self._mnemonic, 16)
		else:
			return scancodes[self._mnemonic]

	@scancode.setter
	@no_notify
	def scancode(self, scancode):
		if scancode == 0:
			self._mnemonic = ""
		else:
			try:
				self._mnemonic = mnemonics[scancode]
			except KeyError:
				self._mnemonic = hex(scancode)
		self._mnemonic_var.set(self._mnemonic)

	def focus(self):
		self._['e_mnemonic'].selection_range(0, END)
		self._['e_mnemonic'].focus_set()

	@property
	def active(self):
		return self._active

	@active.setter
	def active(self, act):
		if act:
			self._active = True
			for w in self._.values():
				w.config(state = NORMAL)
		else:
			self._active = False
			for w in self._.values():
				w.config(state = DISABLED)


class PropsFrame(Frame):
	def __init__(self, master, notify = lambda: False, next_button = lambda: False):
		self.should_notify = False
		super(PropsFrame, self).__init__(master)
		self._ = {}
		self.notify = notify
		self.next_button = next_button
		self.widgets = []
		top = Frame(self)
		top.pack(side = TOP, fill = X)
		l = Label(top, text = "mode: ")
		l.grid(column = 0, row = 0, sticky = W)
		self.mode = IntVar()
		self.mode.set(0)
		self.moderadios = []
		for i, t in enumerate(["defined", "inherited"]):
			r = Radiobutton(top, text = t, variable = self.mode, value = i,
					command = self._on_mode_changed)
			r.grid(column = 1+i, row = 0)
			self.moderadios.append(r)
		self._['l_scancode'] = Label(top, text = "scancode: ")
		self._['l_scancode'].grid(column = 0, row = 1)
		self._['e_scancode'] = ScancodeEntry(top, self._on_props_changed)
		self._['e_scancode'].grid(column = 1, row = 1, columnspan = 2)
		acts = Frame(self)
		acts.pack(side = TOP, fill = X)
		self._['l_press'] = Label(acts, text = "key press action: ")
		self._['l_press'].grid(column = 0, row = 0, sticky = N)
		self._['ac_press'] = ActionChooser(acts, on_change = self._on_props_changed)
		self._['ac_press'].grid(column = 1, row = 0)
		self._['l_release'] = Label(acts, text = "key release action: ")
		self._['l_release'].grid(column = 2, row = 0, sticky = N)
		self._['ac_release'] = ActionChooser(acts, on_change = self._on_props_changed)
		self._['ac_release'].grid(column = 3, row = 0)
		self.should_notify = True

	def _on_mode_changed(self):
		if self.mode.get() == 0:
			for w in self._.values():
				w.config(state = NORMAL)
		else:
			for w in self._.values():
				w.config(state = DISABLED)
		if self.should_notify:
			self._on_props_changed()

	def _on_props_changed(self, *args):
		self.notify()

	def load_keydef(self, key):
		old_should = self.should_notify
		self.should_notify = False
		self._['e_scancode'].scancode = key.scancode
		self._['ac_press'].update_action(key.press)
		self._['ac_release'].update_action(key.release)
		if key.inherited:
			self.mode.set(1)
		else:
			self.mode.set(0)
		self._on_mode_changed()
		self.should_notify = old_should
		self._['e_scancode'].focus()

	def get_keydef(self):
		if self.mode.get() == 1:
			return None
		sc = self._['e_scancode'].scancode
		pr = self._['ac_press'].get_action()
		re = self._['ac_release'].get_action()
		return KeyDef(scancode = sc, press = pr, release = re)

	def set_inheritable(self, inh):
		if inh:
			self.moderadios[1].config(state = NORMAL)
		else:
			self.moderadios[1].config(state = DISABLED)

class MainWindow:
	def __init__(self, master, buttons):
		# FIXME: read params from xml...
		self.buttons = buttons
		self.btn_nos = buttons.nos
		self.cur_filename = None
		self.modified = False
		self.layout = Layout(buttons.num_keys, 16)
		master.wm_geometry("800x600+0+0")
		self.master = master
		self.menu = MainMenu(master, self.on_menu_action)
		master.config(menu = self.menu)

		self.status = StatusBar(master)
		self.status.pack(side = BOTTOM, fill = X)

		master.protocol("WM_DELETE_WINDOW", self.on_exit)

		topbar = Frame(master, bd = 1, relief = RAISED)
		topbar.pack(side = TOP, fill = X)
		self.toolbar = Toolbar(topbar, self.on_menu_action, self.status)
		self.toolbar.grid(column = 0, row = 0, stick = W+N+S)
		self.layer = IntVar(master)
		self.layer.set(0)
		fr = Frame(topbar)
		fr.grid(column = 1, row = 0, stick = E+N+S)
		l = Label(fr, text = "Layer: ")
		l.grid(column = 0, row = 0, stick = N+S+W+E)
		Grid.rowconfigure(fr, 0, weight = 1)
		ls = OptionMenu(fr, self.layer, *range(0, 16), command = self.on_change_layer)
		ls.grid(column = 1, row = 0)
		#p = TooltipButton(fr, text = "+", tooltip = "Add layer", statusbar = self.status,
		#		command = self.on_add_layer)
		#p.grid(column = 2, row = 0)
		#m = TooltipButton(fr, text = "-", tooltip = "Remove layer", statusbar = self.status,
		#		command = self.on_del_layer)
		#m.grid(column = 3, row = 0)
		for i in range(0, 2):
			Grid.columnconfigure(topbar, i, weight = 1)

		f = Frame(master)
		f.pack(side = TOP, fill = X)
		l = Label(f, text = "Inherits from layer: ")
		l.pack(side = LEFT)
		self.inh = StringVar()
		self.inh.set("none")
		self.inhopt = OptionMenu(f, self.inh, "none", command = self.on_change_inh)
		self.inhopt.pack(side = LEFT)
		self.layprops = f
		i = TooltipButton(f, text = "inherit all", tooltip = "Make all keys on this layer inherited", statusbar = self.status,
				command = self.on_inherit_button_clicked)
		i.pack(side = RIGHT)
		self.inherit_btn = i

		self.bottomframe = Frame(master, bd = 1, relief = SUNKEN)

		self.bottomframe.pack(side = BOTTOM, fill = BOTH)

		self.kbframe = KeyboardFrame(master, self.on_key_chosen)
		self.kbframe.pack(side = TOP, fill = BOTH, expand = True)
		master.bind("<Escape>", lambda x: self.on_key_chosen(None))

		self.kbframe.setup_buttons(buttons)

		master.bind("<Control-Return>", lambda x: self.kbframe.next_button())

		self.props = PropsFrame(self.bottomframe,
				notify = self.on_props_changed,
				next_button = self.kbframe.next_button
		)
		self.on_change_layer(self.layer.get())

	def on_inherit_button_clicked(self):
		ans = askyesno("Inherit all keys?", "All key definitions on this layer will be lost. Are you sure?")
		if not ans:
			return
		for i in self.btn_nos :
			b = self.layout[self.layer.get(), i]
			b.inherited = True
			self.kbframe.update_button(i, b)
			self.props.load_keydef(b)

	def on_exit(self):
		if self.modified:
			cont = self.ask_save()
			if not cont:
				return
		self.master.quit()

	def place_frames(self):
		self.topframe.place(y = 0, relheight = self.split, relwidth = 1)
		self.bottomframe.place(rely = self.split, relheight = 1.0-self.split, relwidth = 1)
		self.adjuster.place(relx = 0.9, rely = self.split, anchor = E)

	def say_hi(self):
		print("hi there, everyone!")

	def callback(self):
		self.status.set("hello, %i" % 4)

	def set_save_state(self, st):
		self.menu.set_save_state(st)
		self.toolbar.set_save_state(st)

	def on_key_chosen(self, no):
		self.kbframe.set_current_btn(no)
		if no is None:
			self.props.pack_forget()
		else:
			self.props.pack(side = TOP, fill = X)
			kd = self.layout[self.layer.get(), no]
			self.props.load_keydef(kd)

	def on_change_inh(self, lay):
		if lay == "none":
			lay = -1
		else:
			lay = int(lay)
		self.layout.parents[self.layer.get()] = lay
		self.on_change_layer(self.layer.get())
		self.modified = True
		self.status.set("Layout modified")
		if self.cur_filename is not None:
			self.set_save_state(True)

	def on_props_changed(self):
		cur_no = self.kbframe.get_current_btn()
		kd = self.props.get_keydef()
		if kd is None:
			kd = KeyDef(layout = self.layout, no = cur_no, layer = self.layer.get(),
					inherited = True)
		self.kbframe.update_button(cur_no, kd)
		self.layout[self.layer.get(), cur_no] = kd
		self.modified = True
		self.status.set("Layout modified")
		if self.cur_filename is not None:
			self.set_save_state(True)

	def on_change_layer(self, l):
		if l == 0:
			self.inherit_btn.config(state = DISABLED)
		else:
			self.inherit_btn.config(state = NORMAL)
		for b in self.btn_nos:
			try:
				kd = self.layout[l, b]
				self.kbframe.update_button(b, kd)
			except KeyError:
				pass
		# reload button props on the new layer
		self.on_key_chosen(self.kbframe.get_current_btn())
		if platform_windows():
			for b in self.btn_nos:
				self.kbframe._get_btn_widget(b)._layout_labels()
		self.inhopt.pack_forget()
		opts = [str(i) for i in range(0, l)]
		if l == 0:
			opts = ["none"] + opts
		self.inhopt = OptionMenu(self.layprops, self.inh, *opts, command = self.on_change_inh)
		self.inhopt.pack(side = LEFT)
		if self.layout.parents[l] == -1:
			self.inh.set("none")
		else:
			self.inh.set(str(self.layout.parents[l]))
		self.props.set_inheritable(self.inh.get() != "none")

	def on_add_layer(self):
		pass

	def on_del_layer(self):
		pass

	def on_menu_action(self, cmd):
		if cmd == "saveas":
			fname = asksaveasfilename(filetypes =
					(("Keyboard layout files", "*.lay"), ("All files", "*.*"))
			)
			if fname == "":
				return
			try:
				f = open(fname, "wb")
				f.write(self.layout.binary())
				f.close()
				self.status.set("Saved as: %s." % fname)
				self.cur_filename = fname
				self.set_save_state(False)
				self.modified = False
			except Exception as e:
				self.status.set("Failed to write file %s: %s!" % (fname, str(e)))
		elif cmd == "save":
			try:
				f = open(self.cur_filename, "wb")
				f.write(self.layout.binary())
				f.close()
				self.status.set("Saved.")
				self.set_save_state(False)
				self.modified = False
			except Exception as e:
				self.status.set("Failed to write file %s: %s!" % (fname, str(e)))
		elif cmd == "open":
			if self.modified:
				cont = self.ask_save()
				if not cont:
					return
			fname = askopenfilename(filetypes =
					(("Keyboard layout files", "*.lay"), ("All files", "*.*"))
			)
			if fname == "":
				return
			try:
				f = open(fname, "rb")
				data = f.read()
				self.layout = Layout.from_binary(data)
				self.layer.set(0)
				self.on_change_layer(0)
				self.cur_filename = fname
				self.set_save_state(False)
				self.on_key_chosen(None)
				self.status.set("Opened file: %s" % fname)
			except Exception as e:
				self.status.set("Error opening file: %s" % str(e))
		elif cmd == "new":
			if self.modified:
				cont = self.ask_save()
				if not cont:
					return
			# FIXME: take that from xml
			self.layout = Layout(self.buttons.num_keys, 16)
			self.layer.set(0)
			self.on_change_layer(0)
			self.cur_filename = None
			self.set_save_state(False)
			self.status.set("Created new layout")
		elif cmd == "generate":
			fname = asksaveasfilename(filetypes =
					(("iHex files", "*.hex"), ("All files", "*.*"))
			)
			if fname == "":
				return
			fi = "base_firmware.hex"
			try:
				f = open(fi, "r")
				firmware = f.readlines()
				f.close()
			except Exception as e:
				self.status.set("Failed to read firmware file %s: %s!" % (fi, str(e)))
			blob = "".join(firmware)
			h = hashlib.sha1(bytes(blob, encoding="utf-8")).hexdigest()
			#if h != "22b1fdf1bbf6b8dce8d9a5ba3bf91f842ec067f8":
			#	self.status.set("Corrupted firmware file %s!" % fi)
			#	return

			b = self.layout.binary(fordevice = True)
			chunks = [b[i:i+16] for i in range(0, len(b), 16)]
			lines = []
			for i, chunk in enumerate(chunks):
				data = "".join(map(lambda b: "%.2X" % b, chunk))
				addr = 0x2700+16*i
				chksum = ((((sum(chunk)+len(chunk)+(addr&0xFF)+(addr>>8)) & 0xFF) ^ 0xFF) + 1) & 0xFF
				l = ":%.2X%.4X00%s%.2X\n" % (len(chunk), addr, data, chksum)
				lines.append(l)
			output = firmware[:-1] + lines + [firmware[-1]]
			output = "".join(output)
			try:
				f = open(fname, "w")
				f.write(output)
				f.close()
				self.status.set("Generated firmware %s." % fname)
			except Exception as e:
				self.status.set("Failed to write file %s: %s!" % (fname, str(e)))
		elif cmd == "exit":
			self.on_exit()
		elif cmd == "program":
			u = UKBDC()
			try:
				binary = self.layout.binary(fordevice = True)
				u.attach()
				u.program_layout(binary)
				u.detach()
				self.status.set("Programmed %i bytes of layout" % len(binary))
			except USBError as e:
				self.status.set("Programming error: %s" % str(e))

	def ask_save(self):
		ans = askyesnocancel("Layout modified", "Save modified layout?")
		if ans is None:
			return False
		elif ans and self.cur_filename is not None:
			self.on_menu_action("save")
		elif ans and self.cur_filename is None:
			self.on_menu_action("saveas")
		return True


class MainMenu(Menu):
	def __init__(self, master, command):
		super(MainMenu, self).__init__(master)

		self.filemenu = Menu(self, tearoff = False)
		self.add_cascade(label = "File", menu = self.filemenu)
		self.filemenu.add_command(label = "New", command = lambda: command("new"))
		self.filemenu.add_command(label = "Open...", command = lambda: command("open"))
		self.filemenu.add_command(label = "Save", command = lambda: command("save"))
		self.filemenu.add_command(label = "Save as...", command = lambda: command("saveas"))
		self.filemenu.add_command(label = "Generate firmware...", command = lambda: command("generate"))
		self.filemenu.add_separator()
		self.filemenu.add_command(label = "Exit", command = lambda: command("exit"))
		self.set_save_state(False)

		devmenu = Menu(self, tearoff = False)
		self.add_cascade(label = "Device", menu = devmenu)
		devmenu.add_command(label = "Program", command = lambda: command("program"))

		helpmenu = Menu(self, tearoff = False)
		self.add_cascade(label = "Help", menu = helpmenu)
		helpmenu.add_command(label = "About...", command = lambda: command("about"))

	# Public API starts here...

	def set_save_state(self, st):
		if st:
			self.filemenu.entryconfig(2, state = NORMAL)
		else:
			self.filemenu.entryconfig(2, state = DISABLED)

class TooltipButton(Button):
	def __init__(self, *args, statusbar = None, tooltip = None, **kwargs):
		super(TooltipButton, self).__init__(*args, **kwargs)
		self._tooltip = tooltip
		if statusbar == None:
			raise ValueError("statusbar can't be None")
		else:
			self._statusbar = statusbar
		self.bind("<Enter>", self.on_enter)
		self.bind("<Leave>", self.on_leave)

	@property
	def tooltip(self):
		return self._tooltip

	@tooltip.setter
	def tooltip(self, val):
		self._tooltip = val

	def on_enter(self, ev):
		if self.tooltip is not None:
			self._statusbar.set_tip(self.tooltip)

	def on_leave(self, ev):
		if self.tooltip is not None:
			self._statusbar.clear_tip()


class Toolbar(Frame):
	def __init__(self, master, command, statusbar):
		super(Toolbar, self).__init__(master)
		self._statusbar = statusbar
		img = PhotoImage(file = "icons/save.gif")
		self.save = TooltipButton(self,
				text = "save", image = img,
				command = lambda: command("save"),
				tooltip = "Save current layout",
				statusbar = self._statusbar
		)
		self.save.img = img
		self.save.pack(side = LEFT, padx = 1, pady = 1)
		img = PhotoImage(file = "icons/program.gif")
		self.program = TooltipButton(self,
				text = "program", image = img,
				command = lambda: command("program"),
				tooltip = "Write layout to device",
				statusbar = self._statusbar
		)
		self.program.img = img
		self.program.pack(side = LEFT, padx = 1, pady = 1)
		self.set_save_state(False)

	def set_save_state(self, st):
		if st:
			self.save.config(state = NORMAL)
		else:
			self.save.config(state = DISABLED)


class StatusBar(Frame):
	def __init__(self, master):
		Frame.__init__(self, master)
		self.label = Label(self, bd = 1, relief = SUNKEN, anchor = W)
		self.label.pack(side = LEFT, fill = BOTH, expand = True)
		self.last_status = ""

	def set(self, status):
		self.last_status = status
		self.label.config(text = status)

	def set_tip(self, tip):
		self.label.config(text = tip)

	def clear_tip(self):
		self.label.config(text = self.last_status)

	def clear(self):
		self.label.config(text = "")
		self.last_status = ""


tree = ET.parse("gh60.xml")
keyboard = tree.getroot()
w = int(keyboard.attrib['width'])
h = int(keyboard.attrib['height'])
num_keys = int(keyboard.attrib['num_keys'])
buttons = Buttons(num_keys, w, h)
for key in keyboard:
	no = int(key.attrib['id'])
	buttons.add_button(no,
			int(key.attrib['width']), int(key.attrib['height']),
			int(key.attrib['x']), int(key.attrib['y']))

root = Tk()

#app = ScancodeEntry(root, lambda: 0)
#app.pack()
#root.mainloop()

#exit()

app = MainWindow(root, buttons)

root.mainloop()
