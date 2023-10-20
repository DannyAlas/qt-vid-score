
__version__ = "0.0.1"

import logging
import sys
from qtpy.QtWidgets import QApplication
from video_scoring import MainWindow
import traceback as tb
import qdarktheme

log = logging.getLogger()

def logging_exept_hook(exctype, value, trace):
    log.critical(f"{str(exctype).upper()}: {value}\n\t{tb.format_exc()}")
    sys.__excepthook__(exctype, value, trace)

sys.excepthook = logging_exept_hook


if __name__ == "__main__":

    app = QApplication(sys.argv)
    main_window = MainWindow()

    qss = """
    * {
        font-size: 12px;
    }
    QToolTip {
        font-size: 12px;
        color: #000000;
    }
    QTreeWidget {
        font-size: 15px;
        font-weight: 400;
    }
    QTreeWidget::item {
        height: 30px;
    }
    QListWidget {
        font-size: 15px;
        font-weight: 400;
    }
    QLabel {
        font-size: 15px;
        font-weight: 600;
    }
    QSpinBox {
        height: 30px;
        font-size: 15;
        font-weight: 400;
    }
    QLineEdit {
        height: 30px;
        font-size: 15px;
        font-weight: 400;
    }
    QComboBox {
        height: 30px;
        font-size: 15;
        font-weight: 400;
    }
    QRangeSlider {
        height: 30px;
        spacing: 10px;
        color: #FFFFFF; 
    }
    QSlider {
        padding: 2px 0;
    }
    QSlider::groove {
        border-radius: 2px;
    }
    QSlider::groove:horizontal {
        height: 4px;
    }
    QSlider::groove:vertical {
        width: 4px;
    }
    QSlider::sub-page:horizontal,
    QSlider::add-page:vertical,
    QSlider::handle {
        background: #D0BCFF;
    }
    QSlider::sub-page:horizontal:disabled,
    QSlider::add-page:vertical:disabled,
    QSlider::handle:disabled {
        background: #D0BCFF;
    }
    QSlider::add-page:horizontal,
    QSlider::handle:hover,
    QSlider::handle:pressed {
        background: #D0BCFF;
    }
    QSlider::handle:horizontal {
        width: 16px;
        height: 8px;
        margin: -6px 0;
        border-radius: 8px;
    }
    QSlider::handle:vertical {
        width: 8px;
        height: 16px;
        margin: 0 -6px;
        border-radius: 8px;
    }


    """
    def load_stylesheet():
        # get the dark theme stylesheet
        stylesheet = qdarktheme.load_stylesheet()
        # a simple qss parser
        # the stylesheet is one string with no newlines
        # remove anything contained within { and }
        d = {}
        opened_curly = 0
        selector_txt = ''
        out = ''
        add_lb = False
        for i, char in enumerate(stylesheet):

            if char == '{':
                opened_curly += 1
                # back track to find the start of the selector if we are at the start of a selector
                if opened_curly == 1:
                    j = i
                    while stylesheet[j] != '}':
                        j -= 1
                    selector_txt = stylesheet[j+1:i]
            if char == '}':
                opened_curly -= 1
                if opened_curly == 0: 
                    add_lb = True
                else: 
                    add_lb = False


            if selector_txt.__contains__('QSlider'):
                out += ""
            else:
                out += char
                if add_lb: 
                    out += '\n'
                    add_lb = False
        return out.replace("""{\nborder:1px solid rgba(63, 64, 66, 1.000);border-radius:4px}""", "").replace("QSlider ", "")
    app.setStyleSheet(load_stylesheet())
    # qdarktheme.setup_theme(theme='auto', corner_shape='rounded', custom_colors={"primary": "#D0BCFF"}, additional_qss=qss)
    main_window.show()
    sys.exit(app.exec())