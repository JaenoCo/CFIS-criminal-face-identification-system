from tkinter import *
from tkinter import ttk
import shutil
import time
from PIL import ImageTk, Image
import sqlite3
from tkinter import filedialog
import tkinter.messagebox as tmsg
import cv2
from subprocess import call


def callTrainer():
    call(["python", "trainer.py"])


if __name__ == "__main__":
    root = Tk()
    root.geometry('1400x800')
    root.minsize(1400, 800)
    root.state("zoomed")
    root.title("CFIS - Criminal Registration System")
    root.configure(bg="#f0f2f5")


Fullname = StringVar()
Fathername = StringVar()
Mothername = StringVar()
Bodymark = StringVar()
dob = StringVar()
Nationality = StringVar()
Crime = StringVar()
gen = IntVar()
rel = StringVar()
blood = StringVar()
file1 = ""


def on_enter(button, color):
    """Button hover effect"""
    button['background'] = color


def on_leave(button, color):
    """Button leave effect"""
    button['background'] = color

def ask():
    value = tmsg.askquestion(
        "CONFIRM REGISTRATION",
        "Please ensure all required fields (*) are filled:\n\n" +
        "• Name\n• Gender\n• Religion\n• Crime\n• Face Image\n\n" +
        "Do you want to proceed with registration?"
    )
    if value == "yes":
        x = databaseEnter()
        if (x == 1):
            tmsg.showinfo("Success", "Criminal record has been registered successfully!")
            root.destroy()
        else:
            tmsg.showerror("Error", "Please fill all required (*) fields before submitting.")


      
###########################################################
# def datasetGenerate():
#    if(databaseEnter()==1):
#       detector=cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
#       cam = cv2.VideoCapture(0)

#       id=getid()
      
#       #print(id)
      
#       sampleNum=0
#       time.sleep(2)
#       while(True):
#           ret, img = cam.read()
#           gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#           faces = detector.detectMultiScale(gray, 1.3, 5)
#           for (x,y,w,h) in faces:
#               cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)
#               #incrementing sample number 
#               sampleNum=sampleNum+1
#               #saving the captured face in the dataset folder
#               cv2.imwrite("dataSet/User."+str(id) +'.'+ str(sampleNum) + ".jpg", gray[y:y+h,x:x+w])
#               cv2.waitKey(100)

#           cv2.imshow('face',img)
#           #wait for 100 miliseconds 
#           cv2.waitKey(1)
#           # break if the sample number is morethan 20
#           if(sampleNum>20):
#               break

#       ret, frame = cam.read()

#       # if ret:
#          # cv2.imwrite("images/user." + str(id) + ".png", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

#       cam.release()
#       cv2.destroyAllWindows()
#       tmsg.showinfo("Success","New Face Recorded Successfully")
#       callTrainer()

#       root.destroy()
   
def getid():
    conn = sqlite3.connect('criminal.db')
    with conn:
        cursor = conn.cursor()
    cursor.execute('select max(ID) from People')
    conn.commit()
    for row in cursor:
        for elem in row:
            x = elem
    return x


def databaseEnter():
    name = Fullname.get()
    father = Fathername.get()
    mother = Mothername.get()
    bl = blood.get()
    if (bl == "Select Blood Group"):
        bl = None
    body = Bodymark.get()
    nat = Nationality.get()
    crime = Crime.get()
    Dob = dob.get()
    gen1 = ""
    gender = gen.get()
    if (gender == 1):
        gen1 = 'Male'
    if (gender == 2):
        gen1 = 'Female'
    religion = rel.get()
    if (religion == "Select Religion"):
        religion = None

    if (name != "" and crime != "" and gen1 != ""):
        conn = sqlite3.connect('criminal.db')
        with conn:
            cursor = conn.cursor()
        cursor.execute('INSERT INTO People (Name,Gender,Father,Mother,Religion,Blood,Bodymark,Nationality,Crime) VALUES(?,?,?,?,?,?,?,?,?)',
                       (name, gen1, father, mother, religion, bl, body, nat, crime))
        conn.commit()
        x = getid()
        file = "images/user." + str(x) + ".png"
        newPath = shutil.copy('temp/1.png', file)
    else:
        return 0
    return 1


# Image preview label
preview_image = None
preview_label = None


def mfileopen():
    global preview_image, preview_label
    file1 = filedialog.askopenfilename(
        title="Select Face Image",
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
    )
    if file1:
        print(file1)
        newPath = shutil.copy(file1, 'temp/1.png')
        image = Image.open('temp/1.png')
        image = image.resize((400, 400), Image.LANCZOS)
        preview_image = ImageTk.PhotoImage(image)
        
        if preview_label:
            preview_label.destroy()
        
        preview_label = Label(
            image_frame,
            image=preview_image,
            bg="white",
            relief=SOLID,
            bd=2
        )
        preview_label.image = preview_image
        preview_label.pack(pady=10)
        
        file_path_label.config(text=f"Selected: {file1.split('/')[-1]}", fg="#28a745")

# ================================ GUI LAYOUT ================================

# Header Frame
header_frame = Frame(root, bg="#16213e", height=80)
header_frame.pack(fill=X)
header_frame.pack_propagate(False)

title_label = Label(
    header_frame,
    text="CRIMINAL REGISTRATION SYSTEM",
    font=("Helvetica", 22, "bold"),
    bg="#16213e",
    fg="#ffffff"
)
title_label.pack(pady=25)

# Main container
main_container = Frame(root, bg="#f0f2f5")
main_container.pack(fill=BOTH, expand=True, padx=40, pady=30)

# Left panel - Form
left_panel = Frame(main_container, bg="white", relief=SOLID, bd=1)
left_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))

# Form title
form_title_frame = Frame(left_panel, bg="#0f3460", height=50)
form_title_frame.pack(fill=X)
form_title_frame.pack_propagate(False)

Label(
    form_title_frame,
    text="Personal Information",
    font=("Helvetica", 14, "bold"),
    bg="#0f3460",
    fg="white"
).pack(pady=12)

# Form content with scrollbar
form_canvas = Canvas(left_panel, bg="white", highlightthickness=0)
scrollbar = ttk.Scrollbar(left_panel, orient="vertical", command=form_canvas.yview)
form_content = Frame(form_canvas, bg="white")

form_content.bind(
    "<Configure>",
    lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all"))
)

form_canvas_window = form_canvas.create_window((0, 0), window=form_content, anchor="nw")
form_canvas.configure(yscrollcommand=scrollbar.set)

# Enable mouse wheel scrolling
def on_mousewheel(event):
    form_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

def bind_mousewheel(event):
    form_canvas.bind_all("<MouseWheel>", on_mousewheel)

def unbind_mousewheel(event):
    form_canvas.unbind_all("<MouseWheel>")

form_canvas.bind('<Enter>', bind_mousewheel)
form_canvas.bind('<Leave>', unbind_mousewheel)

# Make canvas window width match canvas width
def resize_canvas_window(event):
    form_canvas.itemconfig(form_canvas_window, width=event.width)

form_canvas.bind('<Configure>', resize_canvas_window)

form_canvas.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar.pack(side=RIGHT, fill=Y)

# Styling variables
label_font = ("Helvetica", 11, "bold")
entry_font = ("Helvetica", 10)
entry_width = 40
padding_y = 15

# Helper function to create form rows
def create_form_row(parent, label_text, variable, row_num, required=False):
    frame = Frame(parent, bg="white")
    frame.pack(fill=X, padx=30, pady=padding_y)
    
    label_txt = label_text + (" *" if required else "")
    label = Label(
        frame,
        text=label_txt,
        font=label_font,
        bg="white",
        fg="#333333" if not required else "#c82333",
        anchor=W
    )
    label.pack(anchor=W)
    
    entry = Entry(
        frame,
        textvariable=variable,
        font=entry_font,
        width=entry_width,
        relief=SOLID,
        bd=1
    )
    entry.pack(fill=X, pady=(5, 0))
    return entry

# Form fields
create_form_row(form_content, "Full Name", Fullname, 0, required=True)
create_form_row(form_content, "Father's Name", Fathername, 1)
create_form_row(form_content, "Mother's Name", Mothername, 2)

# Gender field
gender_frame = Frame(form_content, bg="white")
gender_frame.pack(fill=X, padx=30, pady=padding_y)

Label(
    gender_frame,
    text="Gender *",
    font=label_font,
    bg="white",
    fg="#c82333",
    anchor=W
).pack(anchor=W)

gender_btn_frame = Frame(gender_frame, bg="white")
gender_btn_frame.pack(anchor=W, pady=(5, 0))

Radiobutton(
    gender_btn_frame,
    text="Male",
    variable=gen,
    value=1,
    font=entry_font,
    bg="white",
    activebackground="white",
    relief=FLAT,
    highlightthickness=0,
    bd=0
).pack(side=LEFT, padx=(0, 20))

Radiobutton(
    gender_btn_frame,
    text="Female",
    variable=gen,
    value=2,
    font=entry_font,
    bg="white",
    activebackground="white",
    relief=FLAT,
    highlightthickness=0,
    bd=0
).pack(side=LEFT)

# Religion field
religion_frame = Frame(form_content, bg="white")
religion_frame.pack(fill=X, padx=30, pady=padding_y)

Label(
    religion_frame,
    text="Religion *",
    font=label_font,
    bg="white",
    fg="#c82333",
    anchor=W
).pack(anchor=W)

list1 = ['Hindu', 'Muslim', 'Buddhist', 'Christian', 'Sikh', 'Jain', 'Others']
rel.set('Select Religion')

religion_dropdown = ttk.Combobox(
    religion_frame,
    textvariable=rel,
    values=list1,
    font=entry_font,
    width=entry_width-2,
    state='readonly'
)
religion_dropdown.pack(fill=X, pady=(5, 0))

# Blood Group field
blood_frame = Frame(form_content, bg="white")
blood_frame.pack(fill=X, padx=30, pady=padding_y)

Label(
    blood_frame,
    text="Blood Group",
    font=label_font,
    bg="white",
    fg="#333333",
    anchor=W
).pack(anchor=W)

list2 = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Not known']
blood.set('Select Blood Group')

blood_dropdown = ttk.Combobox(
    blood_frame,
    textvariable=blood,
    values=list2,
    font=entry_font,
    width=entry_width-2,
    state='readonly'
)
blood_dropdown.pack(fill=X, pady=(5, 0))

create_form_row(form_content, "Body Mark", Bodymark, 6)
create_form_row(form_content, "Nationality", Nationality, 7)
create_form_row(form_content, "Crime Convicted", Crime, 8, required=True)

# Add bottom padding to ensure last fields are fully visible
Frame(form_content, bg="white", height=20).pack()

# Right panel - Image upload
right_panel = Frame(main_container, bg="white", relief=SOLID, bd=1, width=450)
right_panel.pack(side=RIGHT, fill=BOTH)
right_panel.pack_propagate(False)

# Image section title
image_title_frame = Frame(right_panel, bg="#0f3460", height=50)
image_title_frame.pack(fill=X)
image_title_frame.pack_propagate(False)

Label(
    image_title_frame,
    text="Face Image",
    font=("Helvetica", 14, "bold"),
    bg="#0f3460",
    fg="white"
).pack(pady=12)

# Image frame
image_frame = Frame(right_panel, bg="white")
image_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)

Label(
    image_frame,
    text="Upload Criminal Face Photo *",
    font=("Helvetica", 11, "bold"),
    bg="white",
    fg="#c82333"
).pack(pady=(10, 5))

Label(
    image_frame,
    text="Supported formats: PNG, JPG, JPEG, BMP",
    font=("Helvetica", 9),
    bg="white",
    fg="#6c757d"
).pack()

# Upload button
upload_btn = Button(
    image_frame,
    text="📁 SELECT IMAGE",
    font=("Helvetica", 11, "bold"),
    bg="#0f3460",
    fg="white",
    relief=FLAT,
    cursor="hand2",
    padx=30,
    pady=10,
    command=mfileopen
)
upload_btn.pack(pady=20)
upload_btn.bind("<Enter>", lambda e: on_enter(upload_btn, '#16558f'))
upload_btn.bind("<Leave>", lambda e: on_leave(upload_btn, '#0f3460'))

# File path label
file_path_label = Label(
    image_frame,
    text="No file selected",
    font=("Helvetica", 9),
    bg="white",
    fg="#6c757d"
)
file_path_label.pack()

# Bottom action buttons
action_frame = Frame(root, bg="#f0f2f5")
action_frame.pack(fill=X, padx=40, pady=(0, 30))

# Register button
register_btn = Button(
    action_frame,
    text="✓ REGISTER CRIMINAL",
    font=("Helvetica", 12, "bold"),
    bg="#28a745",
    fg="white",
    relief=FLAT,
    cursor="hand2",
    padx=40,
    pady=12,
    command=ask
)
register_btn.pack(side=RIGHT)
register_btn.bind("<Enter>", lambda e: on_enter(register_btn, '#218838'))
register_btn.bind("<Leave>", lambda e: on_leave(register_btn, '#28a745'))

# Cancel button
cancel_btn = Button(
    action_frame,
    text="✕ CANCEL",
    font=("Helvetica", 12, "bold"),
    bg="#6c757d",
    fg="white",
    relief=FLAT,
    cursor="hand2",
    padx=40,
    pady=12,
    command=root.destroy
)
cancel_btn.pack(side=RIGHT, padx=(0, 15))
cancel_btn.bind("<Enter>", lambda e: on_enter(cancel_btn, '#5a6268'))
cancel_btn.bind("<Leave>", lambda e: on_leave(cancel_btn, '#6c757d'))

# Info label
info_label = Label(
    action_frame,
    text="Fields marked with * are mandatory",
    font=("Helvetica", 9),
    bg="#f0f2f5",
    fg="#6c757d"
)
info_label.pack(side=LEFT)

root.mainloop()
