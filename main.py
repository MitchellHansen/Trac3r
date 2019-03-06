from tkinter import *
from tkinter import filedialog
from tkinter.ttk import Notebook

from PIL import Image, ImageTk
import subprocess, os, time

from Renderer import Renderer
from Svg2GcodeConverter import Svg2GcodeConverter


class Settings:

    def __init__(self):

        # Height at which the pen touches and draws on the surface
        self.touch_height = 12
        # How far to raise the pen tip to raise it off the page
        self.raise_height = 2
        # The inherent offset from true 0 we have from the pen bracket
        self.head_x_offset = 50
        # XY movement speed
        self.speed = 1000
        # Whether we render lift markers
        self.lift_markers = False

        # X and Y offsets to place the image on A11 paper
        self.offset_x = 70 + self.head_x_offset
        self.offset_y = 20

        # Bed dimensions to fit A11 paper
        self.bed_max_x = 300 - 70 + self.head_x_offset + 20  # 20 is to adjust for the misalignment of print bed
        self.bed_min_x = self.offset_x
        self.bed_max_y = 280
        self.bed_min_y = 20

        self.bed_actual_x = 300
        self.bed_actual_y = 300

        self.lift_counter = 0


class Tracer(Tk):

    def update_highpass_value(self, value):
        self.highpass_filter = value

    def update_blur_value(self, value):
        self.blur = value

    def __init__(self):

        super().__init__()

        # Setup the file structure
        if not os.path.exists("output"):
            os.makedirs("output")
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

        self.settings = Settings()

        self.filename = None

        self.cairo_renderer = Renderer(self.settings)
        self.gcode_converter = Svg2GcodeConverter(self.settings)

        self.highpass_filter = 0
        self.blur = 0

        self.label = None
        self.pix = None
        self.label1 = None
        self.image_ref = None

        # Initialize TK
        self.geometry("{}x{}".format(500, 500))

        self.n = Notebook(self, width= 400, height =400)
        self.n.pack(fill=BOTH, expand=1)

        self.f1 = Frame(self.n)
        self.f2 = Frame(self.n)

        self.rightframe = Frame(self)
        self.rightframe.pack(side=RIGHT)

        self.button = Button(self.rightframe, text="Select Image", command=self.file_select_callback)
        self.button.pack()

        self.button = Button(self.rightframe, text="Re-Render", command=self.render)
        self.button.pack()

        self.lift_markers_checkbox = Checkbutton(self.rightframe, text="Lift Markers", command=self.cairo_renderer.toggle_flip_markers)
        self.lift_markers_checkbox.pack()

        self.highpass_slider = Scale(self.rightframe, command=self.update_highpass_value, resolution=0.1, to=15)
        self.highpass_slider.set(self.highpass_filter)
        self.highpass_slider.pack()

        self.blur_slider = Scale(self.rightframe, command=self.update_blur_value, resolution=0.1, to=5)
        self.blur_slider.set(self.blur)
        self.blur_slider.pack()

        # Start TK
        self.mainloop()

    def file_select_callback(self):
        filepath = filedialog.askopenfilename(initialdir=".", title="Select file",
                                                   filetypes=(("jpeg files", "*.jpg"), ("all files", "*.*")))

        # User didn't select a file
        if len(filepath) is 0:
            return

        self.update_idletasks()

        self.filename = os.path.basename(filepath)

        self.render()

    def render(self):
        self.convert_image(self.filename)
        self.gcode_converter.convert_gcode()

        self.cairo_renderer.clear_screen()
        self.cairo_renderer.render_gcode()

        self.f1.pack_forget()
        self.f2.pack_forget()

        if self.label is not None:
            self.label.pack_forget()
        if self.label1 is not None:
            self.label1.pack_forget()

        pil_image = Image.open("tmp/rendered-output.png")

      #  scale = self.winfo_width() / pil_image.width
      #  pil_image = pil_image.resize((int(scale * pil_image.width), int(scale * pil_image.height)))
        self.image_ref = ImageTk.PhotoImage(pil_image)
        self.label = Label(self.f1, image=self.image_ref)
        self.n.add(self.f1, text="Converted")
        self.label.pack(expand=True, fill="both")

        self.pic = ImageTk.PhotoImage(file="input-images/{}".format(self.filename))

        self.label1 = Label(self.f2, image=self.pic)
        self.n.add(self.f2, text="Original")
        self.label1.pack(expand=True, fill="both")


    # This function takes a file and runs it through mogrify, mkbitmap, and finally potrace.
    # The flow of the intermediate files is
    # input_file.extension  : The input file
    # input_file.bmp        : The input file converted to bmp
    # input_file-n.bmp      : The bmp file after running through some filters
    # input_file.svg        : The output svg render
    def convert_image(self, file_name):

        base_name = file_name.split(".")[0]

        print("Converting input file [{}]".format(file_name))

        print("Running mogrify...")
        start = time.time()
        subprocess.call(["mogrify", "-format", "bmp", "input-images/{}".format(file_name)])
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running mkbitmap...")
        start = time.time()
        mkbitmap_args = ["mkbitmap", "input-images/{}.bmp".format(base_name),
                         "-o", "input-images/{}-n.pbm".format(base_name)]
        if self.highpass_filter > 0:
            mkbitmap_args.append(["-f", self.highpass_filter])

        if self.blur > 0:
            mkbitmap_args.append(["-b", self.blur])


        subprocess.call(mkbitmap_args)
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running potrace...")
        start = time.time()
        subprocess.call(["potrace",
                         #"-t", "0.1",
                         "-z", "white",
                         "-b", "svg",
                         "input-images/{}-n.pbm".format(base_name),
                         "--rotate", "0",
                         "-o", "tmp/conversion-output.svg",
                         ])
        print("Run took [{:.2f}] seconds\n".format(time.time() - start))


if __name__ == "__main__":
    Tracer()

