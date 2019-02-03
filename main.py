#from tkinter import Tk, Label, filedialog, Button, LEFT, RIGHT,
from tkinter import *
from tkinter import filedialog
from tkinter.ttk import Notebook

from PIL import Image, ImageTk
from svgpathtools import svg2paths, Line, QuadraticBezier, CubicBezier
import cairo, subprocess, bezier, os, math, time
import numpy as np

class GCodeConverter:

    def __init__(self, settings):

        self.settings = settings

        # First cycle base case flag
        self.started = False

        self.gcode_preamble = '''
                G91         ; Set to relative mode for the initial pen lift
                G1 Z20      ; Lift head by 20
                G90         ; Set back to absolute position mode
                M107        ; Fan off
                M190 S0     ; Set bed temp
                M104 S0     ; Set nozzle temp
                G28         ; home all axes
                G0 F{1}     ; Set the feed rate
                G1 Z{0}     ; Move the pen to just above the paper
                '''.format(self.settings.touch_height + self.settings.raise_height, self.settings.speed)

        self.gcode_end = '''
                G1 Z{0} F7000   ; Raise the pen high up so we can fit a cap onto it
                M104 S0         ; Set the nozzle to 0
                G28 X0 Y0       ; Home back to (0,0) for (x,y)
                M84             ; Turn off the motors
                '''.format(75)

    # From an input svg file, convert the vector svg paths to gcode tool paths
    def convert_gcode(self):

        # read in the svg
        paths, attributes = svg2paths("tmp/conversion-output.svg")

        # Find the scale value by resizing based on the svg bounding size
        bounding_x_max = None
        bounding_x_min = None
        bounding_y_max = None
        bounding_y_min = None


        for path in paths:

            bbox = path.bbox()

            if bounding_x_max is None:
                bounding_x_max = bbox[0]
            if bounding_x_min is None:
                bounding_x_min = bbox[1]
            if bounding_y_max is None:
                bounding_y_max = bbox[2]
            if bounding_y_min is None:
                bounding_y_min = bbox[3]

            bounding_x_min = min(bbox[0], bounding_x_min)
            bounding_x_max = max(bbox[1], bounding_x_max)

            bounding_y_min = max(bbox[2], bounding_y_min)
            bounding_y_max = max(bbox[3], bounding_y_max)

        print("Maximum X : {:.2f}".format(bounding_x_max))
        print("Minimum Y : {:.2f}".format(bounding_x_min))
        print("Maximum X : {:.2f}".format(bounding_y_max))
        print("Minimum Y : {:.2f}".format(bounding_y_min))

        max_dim = max(bounding_x_max, bounding_x_min, bounding_y_max, bounding_y_min)
        scale = (300 - self.settings.offset_x) / max_dim
        print("Scaling to : {:.5f}\n".format(scale))

        # Start the gcode
        gcode = ""
        gcode += self.gcode_preamble

        # Walk through the paths and create the GCODE
        for path in paths:

            previous_x = None
            previous_y = None

            for part in path:

                start = part.start
                end = part.end

                start_x = start.real * scale + self.settings.offset_x
                start_y = start.imag * scale + self.settings.offset_y

                end_x = end.real * scale + self.settings.offset_x
                end_y = end.imag * scale + self.settings.offset_y

                # Check to see if the endpoint of the last cycle continues and whether we need to lift the pen or not
                lift = True
                if previous_x is not None and previous_y is not None:
                    if abs(start.real - previous_x) < 30 and abs(start.imag - previous_y) < 30:
                        lift = False

                # if the pen needs to lift,
                # if lift:
                previous_x = end.real
                previous_y = end.imag

                if lift:
                    gcode += "G1 Z{:.3f}\n".format(self.settings.raise_height + self.settings.touch_height)
                else:
                    gcode += "# NOT LIFTING [{}]\n".format(self.settings.lift_counter)

                if isinstance(part, CubicBezier):

                    nodes = np.asfortranarray([
                        [start.real, part.control1.real, part.control2.real, end.real],
                        [start.imag, part.control1.imag, part.control2.imag, end.imag],
                    ])

                    curve = bezier.Curve.from_nodes(nodes)

                    evals = []
                    pos = np.linspace(0.1, 1, 10)
                    for i in pos:
                        evals.append(curve.evaluate(i))

                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(start_x, start_y)
                    gcode += "G1 Z{:.3f} \n".format(self.settings.touch_height)

                    for i in evals:
                        x = i[0][0]
                        y = i[1][0]
                        gcode += "G1 X{:.3f} Y{:.3f}\n".format(x * scale + self.settings.offset_x, y * scale + self.settings.offset_y)

                if isinstance(part, Line):
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(start_x, start_y)
                    gcode += "G1 Z{:.3f} \n".format(self.settings.touch_height)
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(end_x, end_y)

        gcode += self.gcode_end

        output_gcode = open("output/gcode-output.gcode", "w")
        output_gcode.write(gcode)
        output_gcode.close()


class CarioSurfaceSettings:

    def __init__(self):

        # Height at which the pen touches and draws on the surface
        self.touch_height = 20
        # How far to raise the pen tip to raise it off the page
        self.raise_height = 2
        # The inherent offset from true 0 we have from the pen bracket
        self.head_x_offset = 50
        # XY movement speed
        self.speed = 500
        # Whether we render lift markers
        self.lift_markers = False

        # X and Y offsets to place the image on A11 paper
        self.offset_x = 75 + self.head_x_offset
        self.offset_y = 20

        # Bed dimensions to fit A11 paper
        self.bed_max_x = 280
        self.bed_min_x = self.offset_x
        self.bed_max_y = 280
        self.bed_min_y = 20
        self.bed_actual_x = 300
        self.bed_actual_y = 300

        self.lift_counter = 0


class CairoSurface():

    def __init__(self, settings):

        self.settings = settings

        self.png_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.svg_surface = cairo.SVGSurface("tmp/rendered-output-t.svg", self.settings.bed_actual_x, self.settings.bed_actual_y)

        self.png_context = cairo.Context(self.png_surface)
        self.png_context.scale(1, 1)
        self.png_context.set_line_width(0.4)

        self.svg_context = cairo.Context(self.svg_surface)
        self.svg_context.scale(1, 1)
        self.svg_context.set_line_width(0.4)

    def clear_screen(self):

        self.png_context.rectangle(0, 0, self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.png_context.set_source_rgba(1, 1, 1, 1.0)
        self.png_context.fill()
        self.png_context.set_source_rgba(0, 0, 0, 1.0)
        self.png_context.stroke()

        self.svg_context.rectangle(0, 0, self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.svg_context.set_source_rgba(1, 1, 1, 1.0)
        self.svg_context.fill()
        self.svg_context.set_source_rgba(0, 0, 0, 1.0)
        self.svg_context.stroke()

    # Render GCODE from the gcode-output.gcode output file that was generated in convert_gcode
    def render_gcode(self):

        file = open("output/gcode-output.gcode", "r")

        largest_x = 0
        largest_y = 0
        smallest_x = 300
        smallest_y = 300
        x = None
        y = None

        for line in file:

            split = line.split(" ")
            command = split[0]
            operands = split[1:]

            prev_x = x
            prev_y = y

            if command == "G1":
                for operand in operands:
                    if operand.startswith("X"):
                        x = float(operand[1:])
                        if x > largest_x: largest_x = x
                        if x < smallest_x: smallest_x = x
                    elif operand.startswith("Y"):
                        y = float(operand[1:])
                        if y > largest_y: largest_y = y
                        if y < smallest_y: smallest_y = y
                    elif operand.startswith("Z{}".format(self.settings.touch_height + self.settings.raise_height)):

                        # signify a lift
                        if prev_x is not None and prev_y is not None and self.settings.lift_markers:
                            self.png_context.arc(prev_x - self.settings.head_x_offset, prev_y, 0.5, 0, 2 * math.pi)
                            self.png_context.stroke()

                            self.svg_context.arc(prev_x - self.settings.head_x_offset, prev_y, 0.5, 0, 2 * math.pi)
                            self.svg_context.stroke()

                            self.svg_context.set_source_rgba(1, 1, 1, 1.0)
                            self.svg_context.select_font_face("Purisa", cairo.FONT_SLANT_NORMAL,
                                                              cairo.FONT_WEIGHT_NORMAL)
                            self.svg_context.set_font_size(3)
                            self.svg_context.move_to(prev_x - self.settings.head_x_offset, prev_y)
                            self.svg_context.show_text(str(self.settings.lift_counter))
                            self.settings.lift_counter += 1
                            self.svg_context.stroke()
                            self.svg_context.set_source_rgba(0, 0, 0, 1.0)

                        prev_x = None
                        prev_y = None
                        x = None
                        y = None

            if (prev_x != x and prev_x is not None) or (prev_y != y and prev_y is not None):
                self.png_context.line_to(prev_x - self.settings.head_x_offset, prev_y)
                self.png_context.line_to(x - self.settings.head_x_offset, y)
                self.png_context.stroke()

                self.svg_context.line_to(prev_x - self.settings.head_x_offset, prev_y)
                self.svg_context.line_to(x - self.settings.head_x_offset, y)
                self.svg_context.stroke()

        print("Largest  X : " + str(largest_x))
        print("Smallest X : " + str(smallest_x))

        print("Largest  Y : " + str(largest_y))
        print("Smallest Y : " + str(smallest_y))

        if largest_x > self.settings.bed_max_x:
            print("X OVERFLOW")
        if largest_y > self.settings.bed_max_y:
            print("Y OVERFLOW")

        if smallest_x < self.settings.bed_min_x:
            print("X_UNDERFLOW")
        if smallest_y < self.settings.bed_min_y:
            print("Y_UNDERFLOW")

        self.save_surfaces()
        # self.init_surfaces()


    def save_surfaces(self):
        self.png_surface.write_to_png('tmp/rendered-output.png')

        # Save the SVG so we can view it, then immediately reopen it so it's ready for a re-render
        self.svg_surface.finish()
        os.rename("tmp/rendered-output-t.svg", "tmp/rendered-output.svg")
        self.svg_surface = cairo.SVGSurface("tmp/rendered-output-t.svg", self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.svg_context = cairo.Context(self.svg_surface)

    # def render(self):
    #     self.clear_screen()
    #     # self.render_gcode()
    #     #
    #     # if self.label is not None:
    #     #     self.label.pack_forget()
    #     #
    #     # # Apply the rendered gcode image to the UI
    #     # self.image_ref = ImageTk.PhotoImage(
    #     #     Image.frombuffer("RGBA", (self.bed_actual_x, self.bed_actual_y), self.png_surface.get_data().tobytes(), "raw", "BGRA", 0, 1))
    #     # self.label = Label(self, image=self.image_ref)
    #     # self.label.pack(expand=True, fill="both")

    def toggle_flip_markers(self):
        self.settings.lift_markers = not self.settings.lift_markers

class GCoder(Tk):


    def update_highpass_value(self, value):
        self.highpass_filter = value


    def __init__(self):

        super().__init__()

        # Setup the file structure
        if not os.path.exists("output"):
            os.makedirs("output")
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

        self.settings = CarioSurfaceSettings()

        self.cairo_renderer = CairoSurface(self.settings)
        self.gcode_converter = GCodeConverter(self.settings)

        self.highpass_filter = 0

        self.label = None
        self.pix = None
        self.label1 = None
        self.image_ref = None

        # Initialize TK
        self.geometry("{}x{}".format(self.settings.bed_actual_x, self.settings.bed_actual_y))

        self.n = Notebook(self, width= 200, height =200)
        self.n.pack(fill=BOTH, expand=1)

        self.f1 = Frame(self.n)
        self.f2 = Frame(self.n)

        self.rightframe = Frame(self)
        self.rightframe.pack(side=RIGHT)

        self.button = Button(self.rightframe, text="Select Image", command=self.file_select_callback)
        self.button.pack()

        self.button = Button(self.rightframe, text="Re-Render", command=self.cairo_renderer.render_gcode)
        self.button.pack()

        self.lift_markers_checkbox = Checkbutton(self.rightframe, text="Lift Markers", command=self.cairo_renderer.toggle_flip_markers)
        self.lift_markers_checkbox.pack()

        self.highpass_slider = Scale(self.rightframe, command=self.update_highpass_value, resolution=0.1, to=15)
        self.highpass_slider.set(self.highpass_filter)
        self.highpass_slider.pack()

        # Start TK
        self.mainloop()

    def file_select_callback(self):
        filepath = filedialog.askopenfilename(initialdir=".", title="Select file",
                                                   filetypes=(("jpeg files", "*.jpg"), ("all files", "*.*")))

        # User didn't select a file
        if len(filepath) is 0:
            return

        self.update_idletasks()

        filename = os.path.basename(filepath)

        self.convert_image(filename)
        self.gcode_converter.convert_gcode()

        self.cairo_renderer.clear_screen()
        self.cairo_renderer.render_gcode()

        self.f1.pack_forget()
        self.f2.pack_forget()

        if self.label is not None:
            self.label.pack_forget()
        if self.label1 is not None:
            self.label1.pack_forget()

        pil_image = Image.frombuffer("RGBA", (self.settings.bed_actual_x, self.settings.bed_actual_y),
                                                             self.cairo_renderer.png_surface.get_data().tobytes(), "raw", "BGRA", 0, 1)
        scale = self.winfo_width() / pil_image.width
        pil_image = pil_image.resize((int(scale * pil_image.width), int(scale * pil_image.height)))
        self.image_ref = ImageTk.PhotoImage(pil_image)
        self.label = Label(self.f1, image=self.image_ref)
        self.n.add(self.f1, text="Converted")
        self.label.pack(expand=True, fill="both")

        self.pic = ImageTk.PhotoImage(file="input-images/{}".format(filename))

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
        subprocess.call(["mkbitmap", "input-images/{}.bmp".format(base_name), "-x",
                       #  "-f", "{}".format(self.highpass_filter),
                         # "-b", "0",
                         "-o", "input-images/{}-n.bmp".format(base_name)
                         ])
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running potrace...")
        start = time.time()
        subprocess.call(["potrace",
                         #"-t", "0.1",
                         "-z", "white",
                         "-b", "svg",
                         "input-images/{}-n.bmp".format(base_name),
                         "--rotate", "0",
                         "-o", "tmp/conversion-output.svg",
                         ])
        print("Run took [{:.2f}] seconds\n".format(time.time() - start))


if __name__ == "__main__":
    GCoder()

