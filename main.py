from tkinter import *
from tkinter import filedialog
from tkinter.ttk import Notebook

from PIL import Image, ImageTk
import os

from GCodeRenderer import Renderer
from Svg2GcodeConverter import Svg2GcodeConverter
from ImageConverter import ImageConverter

class Settings:

    def __init__(self):

        # ============ HARDCODED VALUES ===========

        # Canvas size
        self.canvas_x = 300
        self.canvas_y = 300

        # The position of the pulley centers in relation to the top left and right of the canvas
        self.left_pulley_xy_offset =  (-40, 40)
        self.right_pulley_xy_offset = (40, 40)

        # Diameter of the inner portion of the pulley in millimeters
        self.pulley_diameter = 45

        # Feed rates
        self.speed = 1000

        # Whether we render lift markers
        self.lift_markers = False

        # ============ CALCULATED VALUES ===========

        self.distance_between_centers = abs(self.left_pulley_xy_offset[0]) + self.canvas_x + self.right_pulley_xy_offset[0]




# Main GUI class and program entry point
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

        # Settings for the printer are loaded, TODO: Customize for our dual motor printer
        self.settings = Settings()

        # Image filename which we are converting
        self.filename = None

        # GCODE -> SVG,PNG renderer
        self.cairo_renderer = Renderer(self.settings)

        # SVG -> GCODE converter
        self.gcode_converter = Svg2GcodeConverter(self.settings)

        # FILE -> SVG converter
        self.image_converter = ImageConverter()
        self.image_converter_settings = ImageConverter.ConverterSettings()

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
        self.highpass_slider.set(self.image_converter_settings.highpass_filter)
        self.highpass_slider.pack()

        self.blur_slider = Scale(self.rightframe, command=self.update_blur_value, resolution=0.1, to=5)
        self.blur_slider.set(self.image_converter_settings.blur)
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
        self.image_converter.convert_image(self.filename)
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





if __name__ == "__main__":
    Tracer()

