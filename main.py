from tkinter import *
from tkinter import filedialog
from tkinter.ttk import Notebook

from PIL import Image, ImageTk
import os

from GCodeRenderer import Renderer
from Svg2GcodeConverter import Svg2GcodeConverter, triangulate_lengths, untriangulate_lengths
from ImageConverter import ImageConverter
from Simulator import Simulator


class Settings:

    def __init__(self):

        # ============ HARDCODED VALUES ===========

        # Canvas size
        self.canvas_x = 1000
        self.canvas_y = 1000

        # The position of the pulley centers in relation to the top left and right of the canvas
        self.left_pulley_x_offset  = -40
        self.right_pulley_x_offset =  40
        self.pulley_y_droop = 60

        # Diameter of the inner portion of the pulley in millimeters
        self.pulley_diameter = 45

        # Feed rates
        self.speed = 1000

        # Whether we render lift markers
        self.lift_markers = False
        self.lift_counter = 0
        # ============ CALCULATED VALUES ===========

        self.distance_between_centers = abs(self.left_pulley_x_offset) + self.canvas_x + self.right_pulley_x_offset


# Main GUI class and program entry point
class Tracer(Tk):

    def update_highpass_value(self, value):
        self.highpass_filter = value

    def update_blur_value(self, value):
        self.blur = value

    def update_turd_value(self, value):
        self.turd = value

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
        self.geometry("{}x{}".format(800, 800))

        self.tab_bar = Notebook(self, width= 400, height =400)
        self.tab_bar.pack(fill=BOTH, expand=1)

        self.converted_image_tab = Frame(self.tab_bar)
        self.original_image_tab = Frame(self.tab_bar)

        self.rightframe = Frame(self)
        self.rightframe.pack(side=RIGHT)

        self.centerframe = Frame(self)
        self.centerframe.pack(side=BOTTOM)

        self.image_select_button = Button(self.rightframe, text="Select Image", command=self.file_select_callback)
        self.image_select_button.pack()

        self.rerender_button = Button(self.rightframe, text="Re-Render", command=self.render)
        self.rerender_button.pack()

        self.render_simulation_button = Button(self.rightframe, text="Render Simulation", command=self.render_simulation)
        self.render_simulation_button.pack()

        self.lift_markers_checkbox = Checkbutton(self.rightframe, text="Lift Markers", command=self.cairo_renderer.toggle_flip_markers)
        self.lift_markers_checkbox.pack()

        self.highpass_label = Label(self.centerframe, text="Highpass filter", fg="black")
        self.highpass_label.pack()
        self.highpass_slider = Scale(self.centerframe, command=self.update_highpass_value, resolution=0.0, to=15, orient=HORIZONTAL)
        self.highpass_slider.set(self.image_converter_settings.highpass_filter)
        self.highpass_slider.pack()

        self.blur_label = Label(self.centerframe, text="Blur", fg="black")
        self.blur_label.pack()
        self.blur_slider = Scale(self.centerframe, command=self.update_blur_value, resolution=0.0, to=5, orient=HORIZONTAL)
        self.blur_slider.set(self.image_converter_settings.blur)
        self.blur_slider.pack()

        self.turd_label = Label(self.centerframe, text="Turds", fg="black")
        self.turd_label.pack()
        self.turd_slider = Scale(self.centerframe, command=self.update_turd_value, resolution=0.0, to=5, orient=HORIZONTAL)
        self.turd_slider.set(self.image_converter_settings.turd)
        self.turd_slider.pack()

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
        self.image_converter.convert_image(self.filename, self.image_converter_settings)
        self.gcode_converter.convert_gcode()

        self.cairo_renderer.clear_screen()
        self.cairo_renderer.render_gcode()

        self.converted_image_tab.pack_forget()
        self.original_image_tab.pack_forget()

        if self.label is not None:
            self.label.pack_forget()
        if self.label1 is not None:
            self.label1.pack_forget()

        pil_image = Image.open("tmp/rendered-output.png")

      #  scale = self.winfo_width() / pil_image.width
      #  pil_image = pil_image.resize((int(scale * pil_image.width), int(scale * pil_image.height)))
        self.image_ref = ImageTk.PhotoImage(pil_image)
        self.label = Label(self.converted_image_tab, image=self.image_ref)
        self.tab_bar.add(self.converted_image_tab, text="Converted")
        self.label.pack(expand=True, fill="both")

        self.pic = ImageTk.PhotoImage(file="input-images/{}".format(self.filename))

        self.label1 = Label(self.original_image_tab, image=self.pic)
        self.tab_bar.add(self.original_image_tab, text="Original")
        self.label1.pack(expand=True, fill="both")

    def render_simulation(self):

        simulator = Simulator()
        simulator.render()

settings = Settings()
print(triangulate_lengths(settings, (150, 0)))
# print(triangulate_lengths(settings, (300, 300)))


if __name__ == "__main__":
   Tracer()

