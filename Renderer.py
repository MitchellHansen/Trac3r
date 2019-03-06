import cairo, os, math


class Renderer():

    def __init__(self, settings):

        self.settings = settings

        self.svg_surface = cairo.SVGSurface("tmp/rendered-output-t.svg", self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.svg_context = cairo.Context(self.svg_surface)
        self.svg_context.scale(1, 1)
        self.svg_context.set_line_width(0.1)

    def clear_screen(self):

        self.svg_context.rectangle(0, 0, self.settings.bed_actual_x, self.settings.bed_actual_y)
        self.svg_context.set_source_rgba(1, 1, 1, 1.0)
        self.svg_context.fill()
        self.svg_context.set_source_rgba(0, 0, 0, 1.0)
        self.svg_context.stroke()

        self.svg_context.set_source_rgba(1, 0, 0, 1.0)
        self.svg_context.line_to(self.settings.bed_min_x - self.settings.head_x_offset, self.settings.bed_min_y)
        self.svg_context.line_to(self.settings.bed_max_x - self.settings.head_x_offset, self.settings.bed_min_y)
        self.svg_context.line_to(self.settings.bed_max_x - self.settings.head_x_offset, self.settings.bed_max_y)
        self.svg_context.line_to(self.settings.bed_min_x - self.settings.head_x_offset, self.settings.bed_max_y)
        self.svg_context.line_to(self.settings.bed_min_x - self.settings.head_x_offset, self.settings.bed_min_y)
        self.svg_context.stroke()
        self.svg_context.set_source_rgba(0, 0, 0, 1.0)

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

        self.svg_context.set_source_rgba(0, 0, 1, 1.0)
        self.svg_context.line_to(smallest_x - self.settings.head_x_offset, smallest_y)
        self.svg_context.line_to(largest_x - self.settings.head_x_offset, smallest_y)
        self.svg_context.line_to(largest_x - self.settings.head_x_offset, largest_y)
        self.svg_context.line_to(smallest_x - self.settings.head_x_offset, largest_y)
        self.svg_context.line_to(smallest_x - self.settings.head_x_offset, smallest_y)
        self.svg_context.stroke()
        self.svg_context.set_source_rgba(0, 0, 0, 1.0)

        self.save_surfaces()
        # self.init_surfaces()


    def save_surfaces(self):
        self.svg_surface.write_to_png('tmp/rendered-output.png')

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