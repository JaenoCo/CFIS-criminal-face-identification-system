from tkinter import *
import shutil
from PIL import ImageTk, Image
import sqlite3
from tkinter import filedialog
import tkinter.messagebox as tmsg
from subprocess import call


def register():
    call(["python", "registerGUI.py"])


def VideoSurveillance():
    call(["python", "surveillance.py"])


def detectCriminal():
    call(["python", "detect.py"])


def on_enter(button, color):
    """Button hover effect"""
    button['background'] = color


def on_leave(button, color):
    """Button leave effect"""
    button['background'] = color


# Initialize main window
root = Tk()
root.geometry('900x600')
root.minsize(900, 600)
root.maxsize(900, 600)
root.title("CFIS - Criminal Face Identification System")
root.configure(bg="#1a1a2e")

# Header Frame
header_frame = Frame(root, bg="#16213e", height=100)
header_frame.pack(fill=X)
header_frame.pack_propagate(False)

# Title
title_label = Label(
    header_frame,
    text="CRIMINAL FACE IDENTIFICATION SYSTEM",
    font=("Helvetica", 24, "bold"),
    bg="#16213e",
    fg="#ffffff"
)
title_label.pack(pady=30)

# Subtitle
subtitle_label = Label(
    root,
    text="Advanced Facial Recognition & Security Management",
    font=("Helvetica", 11),
    bg="#1a1a2e",
    fg="#a8a8a8"
)
subtitle_label.pack(pady=(20, 40))

# Main content frame
content_frame = Frame(root, bg="#1a1a2e")
content_frame.pack(expand=True, fill=BOTH, padx=100, pady=20)

# Button styling parameters
btn_width = 35
btn_height = 2
btn_font = ("Helvetica", 12, "bold")
btn_relief = FLAT
btn_cursor = "hand2"

# Register Criminal Button
register_frame = Frame(content_frame, bg="#0f3460", relief=RIDGE, bd=0)
register_frame.pack(pady=15, ipady=5, ipadx=5)

register_btn = Button(
    register_frame,
    text='📋 REGISTER CRIMINAL',
    width=btn_width,
    height=btn_height,
    bg='#0f3460',
    fg='white',
    font=btn_font,
    relief=btn_relief,
    cursor=btn_cursor,
    activebackground="#16558f",
    activeforeground="white",
    command=register
)
register_btn.pack()
register_btn.bind("<Enter>", lambda e: on_enter(register_btn, '#16558f'))
register_btn.bind("<Leave>", lambda e: on_leave(register_btn, '#0f3460'))

# Photo Match Button
detect_frame = Frame(content_frame, bg="#533483", relief=RIDGE, bd=0)
detect_frame.pack(pady=15, ipady=5, ipadx=5)

detect_btn = Button(
    detect_frame,
    text='🔍 PHOTO MATCH',
    width=btn_width,
    height=btn_height,
    bg='#533483',
    fg='white',
    font=btn_font,
    relief=btn_relief,
    cursor=btn_cursor,
    activebackground="#7b4eb5",
    activeforeground="white",
    command=detectCriminal
)
detect_btn.pack()
detect_btn.bind("<Enter>", lambda e: on_enter(detect_btn, '#7b4eb5'))
detect_btn.bind("<Leave>", lambda e: on_leave(detect_btn, '#533483'))

# Video Surveillance Button
surveillance_frame = Frame(content_frame, bg="#c82333", relief=RIDGE, bd=0)
surveillance_frame.pack(pady=15, ipady=5, ipadx=5)

surveillance_btn = Button(
    surveillance_frame,
    text='📹 VIDEO SURVEILLANCE',
    width=btn_width,
    height=btn_height,
    bg='#c82333',
    fg='white',
    font=btn_font,
    relief=btn_relief,
    cursor=btn_cursor,
    activebackground="#e04b4b",
    activeforeground="white",
    command=VideoSurveillance
)
surveillance_btn.pack()
surveillance_btn.bind("<Enter>", lambda e: on_enter(surveillance_btn, '#e04b4b'))
surveillance_btn.bind("<Leave>", lambda e: on_leave(surveillance_btn, '#c82333'))

# Footer
footer_label = Label(
    root,
    text="© 2026 CFIS | Secure • Reliable • Efficient",
    font=("Helvetica", 9),
    bg="#1a1a2e",
    fg="#6c757d"
)
footer_label.pack(side=BOTTOM, pady=15)

root.mainloop()
