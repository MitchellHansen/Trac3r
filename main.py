import math

import numpy as np

touch_height = 20
raise_height = 2
head_x_offset = 50
speed = 500
lift_markers = True

PREAMBLE = '''
G1 Z20
M107
M190 S0
M104 S0
G28 ; home all axes
G0 F{1}
G1 Z{0}
G1 Z{0}
'''.format(touch_height + raise_height, speed)

FINISH = """
G1 Z{0} F7000
M104 S0
G28 X0 Y0
M84
""".format(75)

import cairo, subprocess, bezier, os
from svgpathtools import svg2paths, Line, QuadraticBezier, CubicBezier

# Setup the file structure
if not os.path.exists("output"):
    os.makedirs("output")

# Convert the bmp to a vector svg
file_name = "geom"

subprocess.call(["mogrify", "-format", "bmp", "input-images/{}.svg".format(file_name)])

subprocess.call(["mkbitmap", "input-images/{}.bmp".format(file_name), "-x",
                 "-f", "15",
                 #"-b", "0",
                 "-o", "input-images/{}-n.bmp".format(file_name)
                 ])

subprocess.call(["potrace",
                 "-t", "20",
                 "-z", "white",
                 "-b", "svg",
                 "input-images/{}-n.bmp".format(file_name),
                 "--rotate", "90",
                 "-o", "tmp/conversion-output.svg",
                 ])

# read in the svg
paths, attributes = svg2paths("tmp/conversion-output.svg")

gcode = ""
gcode += PREAMBLE

started = False

scale = 0.0045
offset_x = 75 + head_x_offset
offset_y = 20


# Walk through the paths and create the GCODE
for path in paths:

    previous_x = None
    previous_y = None

   # rotated = path.rotated(90)

    for part in path:

        start = part.start
        end = part.end

        start_x = start.real * scale + offset_x
        start_y = start.imag * scale + offset_y

        end_x = end.real   * scale + offset_x
        end_y = end.imag   * scale + offset_y

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
            gcode += "G1 Z{}\n".format(raise_height + touch_height)
        else:
            gcode += "# NOT LIFTING\n"

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



            gcode += "G1 X{} Y{}\n".format(start_x, start_y)
            gcode += "G1 Z{} \n".format(touch_height)

            for i in evals:
                x = i[0][0]
                y = i[1][0]
                gcode += "G1 X{} Y{}\n".format(x * scale + offset_x, y * scale + offset_y)


            #gcode += "G1 X{} Y{}\n".format(end.real   * scale + offset_x, end.imag   * scale + offset_y)



        if isinstance(part, Line):
            gcode += "G1 X{} Y{}\n".format(start_x, start_y)
            gcode += "G1 Z{} \n".format(touch_height)
            gcode += "G1 X{} Y{}\n".format(end_x, end_y)


gcode += FINISH

output_gcode = open("output/gcode-output.gcode", "w")
output_gcode.write(gcode)
output_gcode.close()

file = open("output/gcode-output.gcode", "r")

x = None
y = None

with cairo.SVGSurface("rendered-output.svg", 300, 300) as surface:

    context = cairo.Context(surface)
    context.scale(1, 1)
    context.set_line_width(0.4)

    largest_x = 0
    largest_y = 0
    smallest_x = 300
    smallest_y = 300

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
                elif operand.startswith("Z{}".format(touch_height + raise_height)):

                    # signify a lift
                    if prev_x is not None and prev_y is not None and lift_markers:
                        context.arc(prev_x, prev_y, 0.5, 0, 2*math.pi)
                        context.stroke()

                    prev_x = None
                    prev_y = None
                    x = None
                    y = None

        if (prev_x != x and prev_x is not None) or (prev_y != y and prev_y is not None):
            context.line_to(prev_x, prev_y)
            context.line_to(x, y)
            context.stroke()


    print("Largest  X : " + str(largest_x))
    print("Largest  Y : " + str(largest_y))
    print("Smallest X : " + str(smallest_x))
    print("Smallest Y : " + str(smallest_y))

    if largest_x > 280:
        print("X OVERFLOW")
    if largest_y > 280:
        print("Y OVERFLOW")

    if smallest_x < 125:
        print("X_UNDERFLOW")
    if smallest_y < 20:
        print("Y_UNDERFLOW")

