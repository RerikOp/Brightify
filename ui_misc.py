import tkinter as tk


class CheckBox(tk.Canvas):
    def __init__(self, master, checked_color, unchecked_color, disabled_color, size=15, *args, **kwargs):
        super().__init__(master, width=size, height=size, *args, **kwargs)
        self.checked_color = checked_color
        self.unchecked_color = unchecked_color
        self.disabled_color = disabled_color

        self.rect = self.create_rectangle(0, 0, size + 2, size + 2, outline=self.unchecked_color,
                                          fill=self.unchecked_color)

        self.is_checked = False
        self._disabled = tk.BooleanVar(value=True)
        self._disabled.trace_add('write', self._on_disabled_change)
        self.command = None

        self.bind("<Button-1>", self.toggle)

    def configure(self, cnf=None, **kwargs):
        if cnf is not None:
            kwargs.update(cnf)

        if "command" in kwargs:
            self.command = kwargs.pop("command")

        tk.Canvas.configure(self, **kwargs)

    # alias
    config = configure

    def toggle(self, event):
        if self._disabled.get():
            return
        self.is_checked = not self.is_checked
        fill_color = self.checked_color if self.is_checked else self.unchecked_color
        self.itemconfig(self.rect, fill=fill_color)
        if self.command:
            self.command(self.is_checked)

    def _on_disabled_change(self, *args):
        fill_color = self.disabled_color if self._disabled.get() else \
            (self.checked_color if self.is_checked else self.unchecked_color)
        self.itemconfig(self.rect, fill=fill_color)
        if not self.disabled and self.command:
            self.command(self.is_checked)

    @property
    def disabled(self):
        return self._disabled.get()

    @disabled.setter
    def disabled(self, value):
        self._disabled.set(value)  # Use .set() to update the value


def show(root: tk.Tk):
    root.grab_release()
    root.deiconify()
    root.focus_force()


def hide(root: tk.Tk):
    root.withdraw()
    root.grab_set()
