import qdarktheme


def load_stylesheet():
    # get the dark theme stylesheet
    stylesheet = qdarktheme.load_stylesheet()

    opened_curly = 0
    selector_txt = ""
    out = ""
    add_lb = False
    for i, char in enumerate(stylesheet):

        if char == "{":
            opened_curly += 1
            # back track to find the start of the selector if we are at the start of a selector
            if opened_curly == 1:
                j = i
                while stylesheet[j] != "}":
                    j -= 1
                selector_txt = stylesheet[j + 1 : i]
        if char == "}":
            opened_curly -= 1
            if opened_curly == 0:
                add_lb = True
            else:
                add_lb = False

        if selector_txt.__contains__("QSlider"):
            out += ""
        else:
            out += char
            if add_lb:
                out += "\n"
                add_lb = False
    return out.replace(
        """{\nborder:1px solid rgba(63, 64, 66, 1.000);border-radius:4px}""", ""
    ).replace("QSlider ", "")


print(load_stylesheet())
