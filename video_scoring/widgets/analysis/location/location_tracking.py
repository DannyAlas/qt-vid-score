########################################################################################
import multiprocessing as mp
import os
from multiprocessing import shared_memory
from typing import List, Literal, Union

import cv2
import numpy as np
import pandas as pd
from pydantic import BaseModel
from qtpy import QtCore, QtGui, QtWidgets
from scipy import ndimage


class ROI(BaseModel):
    uid: str = ""
    mask: Union[None, np.ndarray] = None

    class Config:
        arbitrary_types_allowed = True


class Crop(BaseModel):
    x1: int = 0
    x2: int = 0
    y1: int = 0
    y2: int = 0


class ROI_Analysis(BaseModel):
    threshold: float = 170.0
    method: Literal["dark", "abs", "light"] = "abs"
    roi: ROI = []
    crop: Union[None, Crop] = None
    diff_dict: Union[None, dict[int, bool]] = None


class LocationAnalysis(BaseModel):
    """Represents the data associated with a analysis session"""

    region_names: Union[None, List[str]] = None
    reference: Union[None, np.ndarray] = None
    loc_thresh: float = 99.5
    use_window: bool = True
    window_size: int = 100
    window_weight: float = 0.9
    method: Literal["dark", "abs", "light"] = "dark"
    rmv_wire: bool = False
    wire_krn: int = 5
    location_df: Union[None, pd.DataFrame] = None
    rois: List[ROI] = []
    crop: Union[None, Crop] = None

    class Config:
        arbitrary_types_allowed = True


class AnalysisSettings(BaseModel):
    """Represents the data associated with a analysis session"""

    file: str = ""
    start: int = 0
    end: Union[None, int] = None
    dsmpl: float = 1.0
    reference: Union[None, np.ndarray] = None
    roi_analysis: ROI_Analysis = ROI_Analysis()
    location_analysis: LocationAnalysis = LocationAnalysis()

    class Config:
        arbitrary_types_allowed = True


class LocationTracking(QtCore.QObject):
    def __init__(self, analysis_settings: AnalysisSettings):
        self.anst = analysis_settings

    def set_roi(self):
        cap = cv2.VideoCapture(self.anst.file)  # set file
        # open a cv2 window on the first frame and allow user do draw a region of interest
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # draw a region of interest
        roi = cv2.selectROI(frame)
        cv2.destroyAllWindows()
        # create a mask from the roi
        mask = np.zeros(frame.shape, dtype=np.uint8)
        mask[
            int(roi[1]) : int(roi[1] + roi[3]), int(roi[0]) : int(roi[0] + roi[2])
        ] = 255
        # save the mask
        self.anst.rois.append(ROI(uid="roi", mask=mask))
        # save the video
        cap.release()

    def set_reference(self):
        self.anst.reference = self.Reference()

    def Reference(self, num_frames=1000, frames=None):

        if os.path.isfile(self.anst.file):
            cap = cv2.VideoCapture(self.anst.file)
        else:
            raise FileNotFoundError(
                "File not found. Check that directory and file names are correct."
            )
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Get video dimensions with any cropping applied
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.anst.dsmpl < 1:
            frame = cv2.resize(
                frame,
                (
                    int(frame.shape[1] * self.anst.dsmpl),
                    int(frame.shape[0] * self.anst.dsmpl),
                ),
                cv2.INTER_NEAREST,
            )
        if self.anst.crop is not None:
            frame = frame[
                self.anst.crop.y1 : self.anst.crop.y2,
                self.anst.crop.x1 : self.anst.crop.x2,
            ]

        h, w = frame.shape[0], frame.shape[1]
        cap_max = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_max = int(self.anst.end) if self.anst.end is not None else cap_max

        # Collect subset of frames
        if frames is None:
            # frames = np.random.randint(video_dict['start'],cap_max,num_frames)
            frames = np.linspace(start=self.anst.start, stop=cap_max, num=num_frames)
        else:
            num_frames = len(
                frames
            )  # make sure num_frames equals length of passed list

        collection = np.zeros((num_frames, h, w))
        for (idx, framenum) in enumerate(frames):
            grabbed = False
            while grabbed == False:
                cap.set(cv2.CAP_PROP_POS_FRAMES, framenum)
                ret, frame = cap.read()
                if ret == True:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    if self.anst.dsmpl < 1:
                        gray = cv2.resize(
                            gray,
                            (
                                int(frame.shape[1] * self.anst.dsmpl),
                                int(frame.shape[0] * self.anst.dsmpl),
                            ),
                            cv2.INTER_NEAREST,
                        )

                    collection[idx, :, :] = gray
                    grabbed = True
                elif ret == False:
                    framenum = np.random.randint(self.anst.start, cap_max, 1)[0]
                    pass
        cap.release()

        reference = np.median(collection, axis=0)
        # show the reference frame, converted to uint8
        cv2.imshow("Reference", reference.astype(np.uint8))
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return reference

    def Locate(self, frame: np.ndarray, prior=None):

        # set window dimensions
        if prior != None and self.anst.use_window == True:
            window_size = self.anst.window_size // 2
            ymin, ymax = prior[0] - window_size, prior[0] + window_size
            xmin, xmax = prior[1] - window_size, prior[1] + window_size

        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if self.anst.dsmpl < 1:
                frame = cv2.resize(
                    frame,
                    (
                        int(frame.shape[1] * self.anst.dsmpl),
                        int(frame.shape[0] * self.anst.dsmpl),
                    ),
                    cv2.INTER_NEAREST,
                )

            # find difference from reference
            if self.anst.method == "abs":
                dif = np.absolute(frame - self.anst.reference)
            elif self.anst.method == "light":
                dif = frame - self.anst.reference
            elif self.anst.method == "dark":
                dif = self.anst.reference - frame
            dif = dif.astype("int16")

            # apply window
            weight = 1 - self.anst.window_weight
            if prior != None and self.anst.use_window == True:
                dif = dif + (dif.min() * -1)  # scale so lowest value is 0
                dif_weights = np.ones(dif.shape) * weight
                dif_weights[
                    slice(ymin if ymin > 0 else 0, ymax),
                    slice(xmin if xmin > 0 else 0, xmax),
                ] = 1
                dif = dif * dif_weights

            # threshold differences and find center of mass for remaining values
            dif[dif < np.percentile(dif, self.anst.loc_thresh)] = 0

            # remove influence of wire
            if self.anst.rmv_wire == True:
                ksize = self.anst.wire_krn
                kernel = np.ones((ksize, ksize), np.uint8)
                dif_wirermv = cv2.morphologyEx(dif, cv2.MORPH_OPEN, kernel)
                krn_violation = dif_wirermv.sum() == 0
                dif = dif if krn_violation else dif_wirermv
                if krn_violation:
                    print(
                        "WARNING: wire_krn too large. Reverting to rmv_wire=False for frame"
                    )
            # if there is a difference in any of the rois, set the mask_diff_uid to the uid of the mask that is different
            ret_mask = None
            for mask in self.anst.rois:
                if np.any(dif[mask.mask == 255] != 0):
                    ret_mask = mask
                    break
            com = ndimage.center_of_mass(dif)
            return dif, com, frame, ret_mask

        else:
            return None, None, frame, None

    def TrackLocation(self):
        # load video
        cap = cv2.VideoCapture(self.anst.file)  # set file
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.anst.start)  # set starting frame
        cap_max = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_max = int(self.anst.end) if self.anst.end is not None else cap_max

        # Initialize vector to store motion values in
        X = np.zeros(cap_max - self.anst.start)
        Y = np.zeros(cap_max - self.anst.start)
        D = np.zeros(cap_max - self.anst.start)
        in_mask: list[tuple[int, ROI]] = [None] * (cap_max - self.anst.start)
        # Loop through frames to detect frame by frame differences
        for f in range(len(D)):
            ret, frame = cap.read()
            if f > 0:
                yprior = np.around(Y[f - 1]).astype(int)
                xprior = np.around(X[f - 1]).astype(int)
                dif, com, frame, ret_mask = self.Locate(frame, prior=[yprior, xprior])
            else:
                dif, com, frame, ret_mask = self.Locate(frame)

            if ret == True:
                Y[f] = com[0]
                X[f] = com[1]
                if ret_mask is not None:
                    in_mask[f] = (f, ret_mask)
                    print(f"WARNING: frame {f} is in mask {ret_mask.uid}")
                if f > 0:
                    D[f] = np.sqrt((Y[f] - Y[f - 1]) ** 2 + (X[f] - X[f - 1]) ** 2)
            else:
                # if no frame is detected
                f = f - 1
                X = X[:f]  # Amend length of X vector
                Y = Y[:f]  # Amend length of Y vector
                D = D[:f]  # Amend length of D vector
                break

        # release video
        cap.release()

        # create pandas dataframe
        df = pd.DataFrame(
            {
                "File": self.anst.file,
                "Location_Thresh": np.ones(len(D)) * self.anst.loc_thresh,
                "Use_Window": str(self.anst.use_window),
                "Window_Weight": np.ones(len(D)) * self.anst.window_weight,
                "Window_Size": np.ones(len(D)) * self.anst.window_size,
                "Start_Frame": np.ones(len(D)) * self.anst.start,
                "Frame": np.arange(len(D)),
                "X": X,
                "Y": Y,
                "Distance_px": D,
                "In_Mask": in_mask,
            }
        )

        # #add region of interest info
        # df = ROI_Location(video_dict, df)
        # if video_dict['region_names'] is not None:
        #     print('Defining transitions...')
        #     df['ROI_location'] = ROI_linearize(df[video_dict['region_names']])
        #     df['ROI_transition'] = ROI_transitions(df['ROI_location'])

        # #update scale, if known
        # df = ScaleDistance(video_dict, df=df, column='Distance_px')

        self.anst.location_df = df


class QtProgress:
    def __init__(self, iterable):
        self.iterable = iterable
        self.total = len(iterable)
        self.count = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.count < self.total:
            print(f"{self.count}/{self.total}")
            self.count += 1
            return self.iterable[self.count - 1]
        else:
            raise StopIteration

    def update(self):
        print(f"{self.count}/{self.total}")


class ROIDiff(QtCore.QObject):
    def __init__(self, analysis_settings: AnalysisSettings):
        self.anst = analysis_settings

    def set_roi(self):
        cap = cv2.VideoCapture(self.anst.file)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        roi = cv2.selectROI(frame)
        cv2.destroyAllWindows()
        mask = np.zeros(frame.shape, dtype=np.uint8)
        mask[
            int(roi[1]) : int(roi[1] + roi[3]), int(roi[0]) : int(roi[0] + roi[2])
        ] = 255
        self.roi = mask
        self.crop = Crop(x1=roi[0], x2=roi[0] + roi[2], y1=roi[1], y2=roi[1] + roi[3])
        cap.release()

    def set_reference(self, num_frames=1000):
        if not os.path.isfile(self.anst.file):
            raise FileNotFoundError(
                "File not found. Check that directory and file names are correct."
            )
        cap = cv2.VideoCapture(self.anst.file)
        frames = np.linspace(
            0,
            min(self.anst.end, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))),
            num=num_frames,
            dtype=int,
        )
        collection = []
        for frame_num in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if ret:
                frame = self.crop_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                collection.append(frame)
        self.reference = np.median(collection, axis=0)
        cap.release()

    def crop_frame(self, frame: np.ndarray):
        return frame[self.crop.y1 : self.crop.y2, self.crop.x1 : self.crop.x2]

    def get_dif(self, frame: np.ndarray):
        dif = {
            "abs": np.absolute,
            "light": np.subtract,
            "dark": lambda f, r: np.subtract(r, f),
        }.get(self.method, np.absolute)(frame, self.reference)
        return dif.astype("int16")

    def loop_frames(self):
        frames = np.linspace(0, self.anst.end, num=self.anst.end, dtype=int)
        with mp.Pool(mp.cpu_count()) as pool:
            chunks = np.array_split(frames, mp.cpu_count())
            tasks = [
                pool.apply_async(
                    self.get_in_roi, args=(chunk, self.anst.roi_analysis.threshold)
                )
                for chunk in chunks
            ]
            results = []
            progress = QtProgress(tasks)
            for task in progress:
                results.append(task.get())
        self.anst.roi_analysis.diff_dict = {
            k: v for result in results for k, v in result.items()
        }

    def get_in_roi(self, chunk, threshold: int = 1):
        in_roi = {}
        cap = cv2.VideoCapture(self.anst.file)
        for f in chunk:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ret, frame = cap.read()
            if ret:
                frame = self.crop_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                dif = self.get_dif(frame)
                dif[dif < threshold] = 0
                in_roi[int(f)] = bool(np.any(dif > 0))
        cap.release()
        return in_roi
