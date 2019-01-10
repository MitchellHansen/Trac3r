#from tkinter import Tk, Label, filedialog, Button, LEFT, RIGHT,
from tkinter import *
from tkinter import filedialog
from PIL import Image, ImageTk
from svgpathtools import svg2paths, Line, QuadraticBezier, CubicBezier
import cairo, subprocess, bezier, os, math, time
import numpy as np


class GCoder(Tk):

    def clear_screen(self, ):

        self.png_context.rectangle(0, 0, self.bed_actual_x, self.bed_actual_y)
        self.png_context.set_source_rgba(1, 1, 1, 1.0)
        self.png_context.fill()
        self.png_context.set_source_rgba(0, 0, 0, 1.0)
        self.png_context.stroke()

        self.svg_context.rectangle(0, 0, self.bed_actual_x, self.bed_actual_y)
        self.svg_context.set_source_rgba(1, 1, 1, 1.0)
        self.svg_context.fill()
        self.svg_context.set_source_rgba(0, 0, 0, 1.0)
        self.svg_context.stroke()

    def flip_markers(self):
        self.lift_markers = not self.lift_markers

    def update_highpass_value(self, value):
        self.highpass_filter = value

    def re_render(self):

        self.clear_screen()
        # self.render_gcode()
        #
        # if self.label is not None:
        #     self.label.pack_forget()
        #
        # # Apply the rendered gcode image to the UI
        # self.image_ref = ImageTk.PhotoImage(
        #     Image.frombuffer("RGBA", (self.bed_actual_x, self.bed_actual_y), self.png_surface.get_data().tobytes(), "raw", "BGRA", 0, 1))
        # self.label = Label(self, image=self.image_ref)
        # self.label.pack(expand=True, fill="both")

    def init_surfaces(self):

        self.png_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.bed_actual_x, self.bed_actual_y)
        self.svg_surface = cairo.SVGSurface("tmp/rendered-output-t.svg", self.bed_actual_x, self.bed_actual_y)

        self.png_context = cairo.Context(self.png_surface)
        self.png_context.scale(1, 1)
        self.png_context.set_line_width(0.4)

        self.svg_context = cairo.Context(self.svg_surface)
        self.svg_context.scale(1, 1)
        self.svg_context.set_line_width(0.4)

    def save_surfaces(self):
        self.png_surface.write_to_png('tmp/rendered-output.png')

        # Save the SVG so we can view it, then immediately reopen it so it's ready for a re-render
        self.svg_surface.finish()
        os.rename("tmp/rendered-output-t.svg", "tmp/rendered-output.svg")
        self.svg_surface = cairo.SVGSurface("tmp/rendered-output-t.svg", self.bed_actual_x, self.bed_actual_y)
        self.svg_context = cairo.Context(self.svg_surface)


    def __init__(self):
        super().__init__()

        self.png_surface = None
        self.svg_surface = None
        self.png_context = None
        self.svg_context = None

        # Setup the file structure
        if not os.path.exists("output"):
            os.makedirs("output")
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

        self.highpass_filter = 15

        self.label = None
        self.image_ref = None

        # Height at which the pen touches and draws on the surface
        self.touch_height = 20
        # How far to raise the pen tip to raise it off the page
        self.raise_height = 2
        # The inherent offset from true 0 we have from the pen bracket
        self.head_x_offset = 50
        # XY movement speed
        self.speed = 500
        # Weather we render lift markers
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
        '''.format(self.touch_height + self.raise_height, self.speed)

        self.gcode_end = '''
        G1 Z{0} F7000   ; Raise the pen high up so we can fit a cap onto it
        M104 S0         ; Set the nozzle to 0
        G28 X0 Y0       ; Home back to (0,0) for (x,y)
        M84             ; Turn off the motors
        '''.format(75)

        # UI counter for times the pen was lifted
        self.lift_counter = 0

        # Initialize TK
        self.geometry("{}x{}".format(self.bed_actual_x, self.bed_actual_y))

        # UI ELEMENTS
        self.init_surfaces()

        self.rightframe = Frame(self)
        self.rightframe.pack(side=RIGHT)

        self.button = Button(self.rightframe, text="Select Image", command=self.file_select_callback)
        self.button.pack()

        self.button = Button(self.rightframe, text="Re-Render", command=self.re_render)
        self.button.pack()

        self.lift_markers_checkbox = Checkbutton(self.rightframe, text="Lift Markers", command=self.flip_markers)
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

        filename = os.path.basename(filepath)

        self.convert_image(filename)
        self.convert_gcode()

        self.clear_screen()
        self.render_gcode()

        self.image_ref = ImageTk.PhotoImage(Image.frombuffer("RGBA", (self.bed_actual_x, self.bed_actual_y), self.png_surface.get_data().tobytes(), "raw", "BGRA", 0, 1))
        self.label = Label(self, image=self.image_ref)
        self.label.pack(expand=True, fill="both")

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
                         "-f", "{}".format(self.highpass_filter),
                         # "-b", "0",
                         "-o", "input-images/{}-n.bmp".format(base_name)
                         ])
        print("Run took [{:.2f}] seconds".format(time.time() - start))

        print("Running potrace...")
        start = time.time()
        subprocess.call(["potrace",
                         "-t", "20",
                         "-z", "white",
                         "-b", "svg",
                         "input-images/{}-n.bmp".format(base_name),
                         "--rotate", "0",
                         "-o", "tmp/conversion-output.svg",
                         ])
        print("Run took [{:.2f}] seconds\n".format(time.time() - start))

    def convert_gcode(self):

        # read in the svg
        paths, attributes = svg2paths("tmp/conversion-output.svg")

        bounding_x_max = None
        bounding_x_min = None
        bounding_y_max = None
        bounding_y_min = None

        for path in paths:

            bbox = path.bbox()

            if bounding_x_max is None or bbox[0] > bounding_x_max:
                bounding_x_max = bbox[0]
            if bounding_x_min is None or bbox[1] < bounding_x_min:
                bounding_x_min = bbox[1]

            if bounding_y_max is None or bbox[2] > bounding_y_max:
                bounding_y_max = bbox[2]
            if bounding_y_min is None or bbox[3] > bounding_y_min:
                bounding_y_min = bbox[3]

        print("Maximum X : {:.2f}".format(bounding_x_max))
        print("Minimum Y : {:.2f}".format(bounding_x_min))
        print("Maximum X : {:.2f}".format(bounding_y_max))
        print("Minimum Y : {:.2f}".format(bounding_y_min))

        max_dim = max(bounding_x_max, bounding_x_min, bounding_y_max, bounding_y_min)
        scale = (300 - self.offset_x) / max_dim
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

                start_x = start.real * scale + self.offset_x
                start_y = start.imag * scale + self.offset_y

                end_x = end.real * scale + self.offset_x
                end_y = end.imag * scale + self.offset_y

                # Check to see if the endpoint of the last cycle continues and wether we need to lift the pen or not
                lift = True
                if previous_x is not None and previous_y is not None:
                    if abs(start.real - previous_x) < 30 and abs(start.imag - previous_y) < 30:
                        lift = False

                # if the pen needs to lift,
                # if lift:
                previous_x = end.real
                previous_y = end.imag

                if lift:
                    gcode += "G1 Z{:.3f}\n".format(self.raise_height + self.touch_height)
                else:
                    gcode += "# NOT LIFTING [{}]\n".format(self.lift_counter)

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
                    gcode += "G1 Z{:.3f} \n".format(self.touch_height)

                    for i in evals:
                        x = i[0][0]
                        y = i[1][0]
                        gcode += "G1 X{:.3f} Y{:.3f}\n".format(x * scale + self.offset_x, y * scale + self.offset_y)

                if isinstance(part, Line):
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(start_x, start_y)
                    gcode += "G1 Z{:.3f} \n".format(self.touch_height)
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(end_x, end_y)

        gcode += self.gcode_end

        output_gcode = open("output/gcode-output.gcode", "w")
        output_gcode.write(gcode)
        output_gcode.close()

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
                    elif operand.startswith("Z{}".format(self.touch_height + self.raise_height)):

                        # signify a lift
                        if prev_x is not None and prev_y is not None and self.lift_markers:
                            self.png_context.arc(prev_x - self.head_x_offset, prev_y, 0.5, 0, 2 * math.pi)
                            self.png_context.stroke()

                            self.svg_context.arc(prev_x - self.head_x_offset, prev_y, 0.5, 0, 2 * math.pi)
                            self.svg_context.stroke()

                            self.svg_context.set_source_rgba(1, 1, 1, 1.0)
                            self.svg_context.select_font_face("Purisa", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                            self.svg_context.set_font_size(3)
                            self.svg_context.move_to(prev_x - self.head_x_offset, prev_y)
                            self.svg_context.show_text(str(self.lift_counter))
                            self.lift_counter += 1
                            self.svg_context.stroke()
                            self.svg_context.set_source_rgba(0, 0, 0, 1.0)

                        prev_x = None
                        prev_y = None
                        x = None
                        y = None

            if (prev_x != x and prev_x is not None) or (prev_y != y and prev_y is not None):
                self.png_context.line_to(prev_x - self.head_x_offset, prev_y)
                self.png_context.line_to(x - self.head_x_offset, y)
                self.png_context.stroke()

                self.svg_context.line_to(prev_x - self.head_x_offset, prev_y)
                self.svg_context.line_to(x - self.head_x_offset, y)
                self.svg_context.stroke()

        print("Largest  X : " + str(largest_x))
        print("Smallest X : " + str(smallest_x))

        print("Largest  Y : " + str(largest_y))
        print("Smallest Y : " + str(smallest_y))

        if largest_x > self.bed_max_x:
            print("X OVERFLOW")
        if largest_y > self.bed_max_y:
            print("Y OVERFLOW")

        if smallest_x < self.bed_min_x:
            print("X_UNDERFLOW")
        if smallest_y < self.bed_min_y:
            print("Y_UNDERFLOW")

        self.save_surfaces()
        #self.init_surfaces()


if __name__ == "__main__":
    GCoder()

