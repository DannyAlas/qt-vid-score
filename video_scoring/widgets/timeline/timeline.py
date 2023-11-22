
from qtpy.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsLineItem, QFrame, QDockWidget
from qtpy.QtCore import Qt, QRectF, Signal
from qtpy.QtGui import  QPen, QPainter
from typing import TYPE_CHECKING, List 
from video_scoring.widgets.timeline.track import BehaviorTrack
from video_scoring.widgets.timeline.playhead import CustomPlayhead

if TYPE_CHECKING:
    from video_scoring import MainWindow


class TimelineView(QGraphicsView):
    valueChanged = Signal(int)
    frame_width_changed = Signal(int)
    def __init__(self, num_frames, parent:'TimelineDockWidget' = None):
        super().__init__()
        # Set up the scene
        self.setScene(QGraphicsScene(self))
        self.setMouseTracking(True)
        self.parent = parent
        self.value = 0 # Current frame
        self.base_frame_width = 50  # Base width for each frame
        self.frame_width = self.base_frame_width  # Current width for each frame
        self.num_frames = num_frames  # Total number of frames
        self.zoom_factor = 1.1  # Factor for zooming in and out
        self.scale_factor = 1.1  # Zoom factor for X-axis
        self.current_scale_x = 1  # Current scale on X-axis
        self.left_hand_margin = 20 # Left hand margin for the view
        
        self.playing = False  # Whether the mouse wheel is being used
        self.lmb_holding = False  # Whether the left mouse button is being held
        self.dragging_playhead = False  # Whether the playhead is being dragged
        self.item_keys_to_hide: dict[int, 'BehaviorTrack'] = {} # A dict of key for the item to hide and the corresponding behavior track
        self.item_keys_to_render: dict[int, 'BehaviorTrack'] = {} # A dict of key for the item to render and the corresponding behavior track
        self.setSceneRect(0, 0, num_frames * self.frame_width, 60)  # Adjust the size as needed
        # Customize the view
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(QPainter.RenderHint.Antialiasing)

        # Create and add the playhead
        self.playhead = CustomPlayhead(10, 0, 60, self.frame_width, self)  
        self.scene().addItem(self.playhead)
        self.playhead.triangle.signals.valueChanged.connect(self.valueChanged.emit)

        # add a track
        self.track_height = 50
        self.track_y_start = 50

        self.hover_line = QGraphicsLineItem(0, 0, 0, 0)

        ################ TEMP ################
        self.behavior_tracks: List[BehaviorTrack] = []
        self.add_behavior_track("testing")

    def add_behavior_track(self, name: str):
        # add a new behavior track
        # get the y position of the new track
        y_pos = len(self.behavior_tracks) * self.track_height + self.track_y_start
        # create the new track
        track = BehaviorTrack(name, y_pos+30, self.track_height, 'OnsetOffset', self)
        self.behavior_tracks.append(track)
        self.scene().addItem(track)
        # resize the view so that the track we can see the track
        self.resize(self.rect().width(), y_pos + self.track_height + 10)
        self.setMinimumSize(self.rect().width(), y_pos + self.track_height + 10)
        self.scene().update()
        
    def add_oo_behavior(self, onset):
        if self.behavior_tracks[0].curr_behavior_item is None:
            x = self.behavior_tracks[0].check_for_overlap(onset)
            if x is None:
                self.behavior_tracks[0].add_behavior(onset)
                self.scene().update()
            else:
                x.setErrored()
        else:
            self.behavior_tracks[0].curr_behavior_item = None

    def get_item_at_frame(self, frame: int):
        # get the item at a specific frame
        for track in self.behavior_tracks:
            for onset, item in track.behavior_items.items():
                if frame >= onset and frame <= item.offset:
                    return item
        return None

    def set_length(self, length: int):
        self.num_frames = length
        self.setSceneRect(0, 0, length * self.frame_width, 60)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        if self.num_frames > 100:
            self.base_frame_width = 50
            self.frame_width = 5
            self.frame_width_changed.emit(self.frame_width)
        self.scene().update()
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        pen = QPen(Qt.GlobalColor.gray, 1)
        painter.setPen(pen)

        left_start = rect.left()
        
        visible_left_frame = int(left_start / self.frame_width) + 1
        visible_right_frame = int(rect.right() / self.frame_width) + 1

        # Determine skip factor based on frame width
        skip_factor = max(1, int(self.base_frame_width / self.frame_width))
        self.tick_size = 20
        self.top_margin = 25
        self.tick_top = int(self.mapToScene(0, 0).y() + self.top_margin)
        self.tick_bottom = int(self.mapToScene(0, 0).y() + self.tick_size +self.top_margin)

        for i in range(max(0, visible_left_frame), min(visible_right_frame, self.num_frames)):
            if i == 1:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top+5, x, self.tick_bottom-5)
            if i % skip_factor == 0:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top, x, self.tick_bottom)
                rect = QRectF(x - 20, self.tick_bottom, 40, 20)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i))
            else:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top+5, x, self.tick_bottom-5)

    def get_playhead_frame(self):
        # get the current frame the playhead is on
        return int(self.playhead.pos().x() / self.frame_width)

    def get_x_pos_of_frame(self, frame: int) -> int:
        # given a frame, get the x position of that frame in the scene
        return int(frame * self.frame_width)      

    def get_frame_of_x_pos(self, x_pos: float) -> int:
        # get the frame of a position
        snapped_x = round(x_pos / self.frame_width) * self.frame_width
        return int(snapped_x / self.frame_width)

    def get_visable_frames(self):
        # returns a tuple of the left and right visible frames
        left = int(self.mapToScene(0, 0).x() / self.frame_width)
        right = int((self.mapToScene(self.rect().width(), 0).x() / self.frame_width) + 1)
        return left, right

    def move_playhead_to_frame(self, frame):
        # move the playhead to a specific frame
        self.playhead.setPos(abs(self.get_x_pos_of_frame(frame)), 0)
        self.playhead.triangle.current_frame = frame
        if self.behavior_tracks[0].curr_behavior_item is not None:
            x = self.behavior_tracks[0].check_for_overlap(self.behavior_tracks[0].curr_behavior_item.onset, frame)
            if x is None:
                self.behavior_tracks[0].curr_behavior_item.set_offset(frame)
            else:
                x.setErrored()
        self.valueChanged.emit(frame)

    def wheelEvent(self, event):
        # if we're holding ctrl, zoom in or out
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.zoomEvent(event)
        # otherwise, scroll left or right
        else:
            self.scrollEvent(event)

    def zoomEvent(self, event):
        # Zoom in or out by changing the frame width
        # alt switches the angle delta to horizontal, so we use x() instead of y()
        if event.angleDelta().x() > 0:
            # Zoom in (increase frame width)
            # but if we're zoomed in too far, don't zoom in
            if self.frame_width < self.base_frame_width * 10:
                self.frame_width *= self.zoom_factor
        elif event.angleDelta().x() < 0:
            # Zoom out (decrease frame width) 
            # but if we're all the frames can't fit in the view, don't zoom out
            if self.num_frames * self.frame_width > self.rect().width():
                self.frame_width /= self.zoom_factor
        # Update the frame width of the playhead            
        self.playhead.updateFrameWidth(self.frame_width)
        # Update the scene rect to reflect the new total width of the timeline
        total_width = self.num_frames * self.frame_width
        self.setSceneRect(0, 0, total_width, 60)
        # get the mouse position in the scene and scroll towards it
        mouse_pos = self.mapToScene(event.pos())
        # center the view on the mouse position but by a factor of the zoom
        self.centerOn(mouse_pos)
        # Redraw the scene to update the frame display
        # move the playhead to the current frame
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        # Redraw the scene to update the frame display
        self.update()
        self.scene().update()

    def scrollEvent(self, event):
        # Scroll left or right by changing the scene position
        if event.angleDelta().y() > 0:
            # Scroll left
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
        elif event.angleDelta().y() < 0:
            # Scroll right
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
        self.update()
        self.scene().update()

    def scroll_to_playhead(self):
        # get the current position of the playhead
        playhead_pos = self.playhead.pos().x()
        # get the current position of the view
        view_pos = self.horizontalScrollBar().value()
        # get the width of the view
        view_width = self.rect().width()

        # if the playhead is to the left of the view, scroll left
        if playhead_pos <= view_pos:
            # if we can scroll left by the width of the view, do so
            self.horizontalScrollBar().setValue(int(view_width))
            # otherwise, just scroll to the beginning
            if self.horizontalScrollBar().value() == view_pos:
                self.horizontalScrollBar().setValue(0)
            
        # if the playhead is to the right of the view, scroll right so that the playhead is all way to the left
        elif playhead_pos > view_pos + view_width:
            self.horizontalScrollBar().setValue(int(playhead_pos))

    def mouseMoveEvent(self, event):
        mouse_pos = self.mapToScene(event.pos()).x()
        # get the current position of the view
        view_pos = self.horizontalScrollBar().value()
        # get the width of the view
        view_width = self.rect().width()
        if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
            # if the mouse is within the view, draw a vertical line
            # Snap to the nearest frame
            new_x = self.mapToScene(event.pos()).x()
            snapped_x = round(new_x / self.frame_width) * self.frame_width
            self.hover_line.setLine(snapped_x, self.mapToScene(0, 0).y(), snapped_x, self.mapToScene(0, 0).y() + 30)
            # set pen color to light gray
            pen = QPen(Qt.GlobalColor.lightGray, 1)
            self.hover_line.setPen(pen)
            self.hover_line.show()
        # if we're in the top 50 pixels and holding the left mouse button and the playhead triangle is not being hovered over, move the playhead to the current mouse position
        if self.lmb_holding and event.pos().y() < 50:
            self.dragging_playhead = True
        if self.dragging_playhead:
            # get the current position of the mouse
            mouse_pos = self.mapToScene(event.pos()).x()
            # get the current position of the view
            view_pos = self.horizontalScrollBar().value()
            # get the width of the view
            view_width = self.rect().width()
            if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                # if we're holding shift, snap to the nearest behavior onset or offset if it's within 20 pixels
                frame = int(mouse_pos / self.frame_width) + 1
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # get the nearest behavior onset or offset
                    for key, track in self.item_keys_to_render.items():
                        behavior = track.behavior_items[key]
                        if abs(mouse_pos - self.get_x_pos_of_frame(behavior.onset)) < 20:
                            frame = behavior.onset
                            break
                        elif abs(mouse_pos - self.get_x_pos_of_frame(behavior.offset)) < 20:
                            frame = behavior.offset
                            break
                        else:
                            frame = int(mouse_pos / self.frame_width) + 1

                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(frame)
                self.playhead.triangle.pressed = False

        self.scene().update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # if we're in the top 50 pixels, get the frame at the current mouse position and move the playhead to that frame
        if event.pos().y() < 50 and not self.lmb_holding:
            # get the current position of the mouse
            mouse_pos = self.mapToScene(event.pos()).x()
            # get the current position of the view
            view_pos = self.horizontalScrollBar().value()
            # get the width of the view
            view_width = self.rect().width()
            # if the mouse is within the view, draw a vertical line
            if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                frame = int(mouse_pos / self.frame_width) + 1
                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(frame)
                self.playhead.triangle.pressed = False
        self.lmb_holding = True

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        self.dragging_playhead = False
        super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event) -> None:
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())
        self.hover_line.setLine(1, self.mapToScene(0, 0).y(), 1, self.mapToScene(0, 0).y() + 30)
        return super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())

        # if the playhead outside the view, scroll to it so it's visible
        if self.playhead.pos().x() < self.horizontalScrollBar().value() or self.playhead.pos().x() > self.horizontalScrollBar().value() + self.rect().width():
            if not self.playhead.triangle.pressed and self.playing:
                # scroll to the playhead
                self.scroll_to_playhead()

        # if the curr_behavior_item is not None, highlight the item
        if self.behavior_tracks[0].curr_behavior_item is not None:
            self.behavior_tracks[0].curr_behavior_item.highlight()
            
        # get the range of visible frames in the view
        l,r = self.get_visable_frames()
        for track in self.behavior_tracks:
            track.setRect(0, self.mapToScene(0,track.y_position).y(), self.mapToScene(0,0).x() + self.rect().width(), track.track_height)

            for item in track.behavior_items.values():
                if not item.pressed:
                    item.setPos(self.get_x_pos_of_frame(item.onset), self.mapToScene(0,track.y_position).y()+2)
                    item.setRect(0, 0, self.get_x_pos_of_frame(item.offset) - self.get_x_pos_of_frame(item.onset), track.track_height-4)

                    if not item != self.behavior_tracks[0].curr_behavior_item:
                        item.unhighlight()
            ################################ LOD RENDERING ################################

            # get the list of items whos onset and item.offset fall outside the visible range
            self.item_keys_to_hide = {key:track for key in track.behavior_items.keys() if track.behavior_items[key].onset < l and track.behavior_items[key].offset > r}
            self.item_keys_to_render = {key:track for key in track.behavior_items.keys() if key >= l and key <= r}

            # ISSUE: zooming breaks this - items everywhere. 

            # hide the items that are not in the visible range
            # for item in track.behavior_items.values():
            #     if item in self.item_keys_to_hide.values():
            #         item.hide()
                    
            # # show the items that are in the visible range
            # for key in self.item_keys_to_render.keys():
            #     track.behavior_items[key].show()
            #     item = track.behavior_items[key]
            #     if not item.pressed:
            #         item.setPos(self.get_x_pos_of_frame(item.onset), self.mapToScene(0,track.y_position).y()+2)
            #         item.setRect(0, 0, self.get_x_pos_of_frame(item.offset) - self.get_x_pos_of_frame(item.onset), track.track_height-4)

        return super().paintEvent(event)

    def setValue(self, value):
        self.value = value
        self.update()

    def isPlayheadDown(self):
        return self.playhead.triangle.pressed

    def update(self):
        if self.value:
            self.playhead.triangle.current_frame = self.value

        if self.behavior_tracks[0].curr_behavior_item is not None:
            it = self.behavior_tracks[0].curr_behavior_item
            if self.behavior_tracks[0].overlap_with_item_check(it, onset=self.value):
               it.setErrored()
            else:
                self.behavior_tracks[0].curr_behavior_item.set_offset(self.value)
            
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        super().update()

class TimelineDockWidget(QDockWidget):
    """This is the widget that contains the timeline, as a dockwidget for resizing. It cannot be closed or floated, only docked and resized"""
    
    def __init__(self, main_win: "MainWindow", parent=None):
            super(TimelineDockWidget, self).__init__(parent)
            self.setWindowTitle("Timeline")
            self.timeline_view = TimelineView(100, self)
            self.main_win = main_win
            self.setWidget(self.timeline_view)

    def set_length(self, length: int):
        self.timeline_view.set_length(length)

    def move_to_last_onset_offset(self):
        print("move to last onset offset")
        curr_frame = self.timeline_view.get_playhead_frame()
        curr_item = self.timeline_view.get_item_at_frame(curr_frame)
        if curr_item is not None:
            # if we're at the onset, move to the previous items onffset
            if curr_frame == curr_item.onset:
                # get the item before the current item
                for onset, item in reversed(self.timeline_view.behavior_tracks[0].behavior_items.items()):
                    if onset < curr_frame:
                        self.timeline_view.move_playhead_to_frame(item.offset)
                        break
            elif curr_frame == curr_item.offset:
                self.timeline_view.move_playhead_to_frame(curr_item.onset)
            elif curr_frame > curr_item.onset and curr_frame < curr_item.offset:
                self.timeline_view.move_playhead_to_frame(curr_item.onset)
            else:
                self.timeline_view.move_playhead_to_frame(curr_frame)
        else:
            # iterate through the items backwards until we find one that is before the current frame
            for onset, item in reversed(self.timeline_view.behavior_tracks[0].behavior_items.items()):
                if onset < curr_frame:
                    self.timeline_view.move_playhead_to_frame(item.offset)
                    break
            else:
                self.timeline_view.move_playhead_to_frame(curr_frame)

        
    def move_to_next_onset_offset(self):
        print("move to next onset offset")
        curr_frame = self.timeline_view.get_playhead_frame()
        curr_item = self.timeline_view.get_item_at_frame(curr_frame)
        if curr_item is not None:
            # if we're at the onset, move to the previous items onset
            if curr_frame == curr_item.onset:
                self.timeline_view.move_playhead_to_frame(curr_item.offset)
            elif curr_frame == curr_item.offset:
                # get the item after the current item
                for onset, item in self.timeline_view.behavior_tracks[0].behavior_items.items():
                    if onset > curr_frame:
                        self.timeline_view.move_playhead_to_frame(item.onset)
                        break
            elif curr_frame > curr_item.onset and curr_frame < curr_item.offset:
                self.timeline_view.move_playhead_to_frame(curr_item.offset)
            else:
                self.timeline_view.move_playhead_to_frame(curr_frame)
        else:
            # iterate through the items backwards until we find one that is before the current frame
            for onset, item in self.timeline_view.behavior_tracks[0].behavior_items.items():
                if onset > curr_frame:
                    self.timeline_view.move_playhead_to_frame(item.onset)
                    break
            else:
                self.timeline_view.move_playhead_to_frame(curr_frame)


    def move_to_last_timestamp(self):
        pass
    def move_to_next_timestamp(self):
        pass
    def select_current_timestamp(self):
        # get the timestamp at the current frame of the playhead
        # get the item at the current frame
        self.timeline_view.behavior_tracks[0].curr_behavior_item = self.timeline_view.get_item_at_frame(self.timeline_view.get_playhead_frame())

    def delete_selected_timestamp(self):
        pass
