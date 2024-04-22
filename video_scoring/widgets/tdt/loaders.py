import copy
import os
import re
import warnings
from datetime import datetime
from typing import List, Literal, Tuple, Union

import numpy as np
import tdt
from enum import StrEnum
from qtpy.QtCore import QObject
from video_scoring.widgets.tdt._types import Block
from video_scoring.widgets.progress import ProgressSignals

MAX_UINT64 = np.iinfo(np.uint64).max


def time2sample(ts, fs=195312.5, t1=False, t2=False, to_time=False):
    sample = ts * fs
    if t2:
        # drop precision beyond 1e-9
        exact = np.round(sample * 1e9) / 1e9
        sample = np.floor(sample)
        if exact == sample:
            sample -= 1
    else:
        # drop precision beyond 1e-9
        sample = np.round(sample * 1e9) / 1e9
        if t1:
            sample = np.ceil(sample)
        else:
            sample = np.round(sample)
    sample = np.uint64(sample)
    if to_time:
        return np.float64(sample) / fs
    return sample


def snip_maker(data_snip):
    # convert strobe-controlled data snips into larger chunks
    nchunks, chunk_length = data_snip.data.shape

    ts_diffs = np.diff(data_snip.ts, axis=0)
    ts_diffThresh = (chunk_length + 1) / data_snip.fs
    gap_points = np.where(ts_diffs > ts_diffThresh)[0]
    gap_points = np.concatenate([gap_points, [nchunks - 1]])

    snip_store = []
    snip_store_ts = []
    nchan = np.max(data_snip.chan)
    gp_index = 0
    for ind in range(len(gap_points)):
        if nchan == 1:
            chan_index = np.arange(0, gap_points[ind] - gp_index + 1)
            snip_store.append(data_snip.data[gp_index + chan_index, :].flatten())
        else:
            nchunks = int(np.floor((gap_points[ind] - gp_index + 1) / nchan))
            chan_mat = np.zeros((nchan, nchunks * chunk_length))
            for chan in range(nchan):
                chan_index = np.where(
                    data_snip.chan[gp_index : gap_points[ind] + 1] == chan + 1
                )[0]
                if len(chan_index) != nchunks:
                    warnings.warn(
                        "channel {0} was shortened to {1} chunks".format(chan, nchunks),
                        Warning,
                        stacklevel=2,
                    )
                chan_index = chan_index[:nchunks]
                chan_mat[chan, :] = data_snip.data[gp_index + chan_index, :].flatten()
            snip_store.append(chan_mat)
        snip_store_ts.append(data_snip.ts[gp_index])
        gp_index = gap_points[ind] + 1

    data_snip.data = snip_store
    data_snip.ts = snip_store_ts
    data_snip.chan = np.arange(nchan)
    return data_snip


def parse_tbk(tbk_path):
    block_notes = []
    try:
        with open(tbk_path, "rb") as tbk:
            s = tbk.read().decode("cp437")

        # create array of structs with store information
        # split block notes into rows

        delimInd = [m.start() for m in re.finditer("\[USERNOTEDELIMITER\]", s)]
        s = s[delimInd[1] : delimInd[2]].replace("[USERNOTEDELIMITER]", "")

        lines = s.split("\n")
        lines = lines[:-1]

        # loop through rows
        temp_store = tdt.StructType()
        first_pass = True
        for line in lines:
            # check if this is a new store
            if "StoreName" in line:
                # save previous store into block_notes
                if first_pass:
                    first_pass = False
                else:
                    block_notes.append(temp_store)
                temp_store = tdt.StructType()

            # find delimiters
            parts = line.split(";")[:-1]

            # grab field and value between the '=' and ';'
            field_str = parts[0].split("=")[-1]
            value = parts[-1].split("=")[-1]

            # insert new field and value into store struct
            setattr(temp_store, field_str, value)

    except:
        warnings.warn(
            "Bad tbk file, try running the TankRestore tool to correct. See https://www.tdt.com/docs/technotes/#tn0935",
            Warning,
            stacklevel=2,
        )
        return []

    # insert last store in notes
    if len(temp_store.items()) > 0:
        block_notes.append(temp_store)

    return block_notes


def code_to_type(code):
    # given event code, return string 'epocs', 'snips', 'streams', or 'scalars'
    strobe_types = [tdt.EVTYPE_STRON, tdt.EVTYPE_STROFF, tdt.EVTYPE_MARK]
    scalar_types = [tdt.EVTYPE_SCALAR]
    snip_types = [tdt.EVTYPE_SNIP]

    if code in strobe_types:
        s = "epocs"
    elif code in snip_types:
        s = "snips"
    elif code & tdt.EVTYPE_MASK == tdt.EVTYPE_STREAM:
        s = "streams"
    elif code in scalar_types:
        s = "scalars"
    else:
        s = "unknown"
    return s


def check_ucf(code):
    # given event code, check if it has unique channel files
    return code & tdt.EVTYPE_UCF == tdt.EVTYPE_UCF


def code_to_name(code):
    return int(code).to_bytes(4, byteorder="little").decode("cp437")


def epoc_to_type(code):
    # given epoc event code, return if it is 'onset' or 'offset' event

    strobe_on_types = [tdt.EVTYPE_STRON, tdt.EVTYPE_MARK]
    strobe_off_types = [tdt.EVTYPE_STROFF]
    if code in strobe_on_types:
        return "onset"
    elif code in strobe_off_types:
        return "offset"
    return "unknown"


def read_sev(
    sev_dir,
    *,
    channel=0,
    event_name="",
    t1=0,
    t2=0,
    fs=0,
    ranges=None,
    verbose=0,
    just_names=0,
    scale=1,
):
    """TDT sev file data extraction.

    data = read_sev(sev_dir), where sev_dir is a string, retrieves
    all sev data from specified directory in struct format. sev_dir can
    also be a single file. SEV files are generated by an RS4 Data Streamer,
    or by enabling the Discrete Files option in the Synapse Stream Data
    Storage gizmo, or by setting the Unique Channel Files option in
    Stream_Store_MC or Stream_Store_MC2 macro to Yes in OpenEx.

    If exporting is enabled, this function returns None.

    data    contains all continuous data (sampling rate and raw data)

    optional keyword arguments:
        t1          scalar, retrieve data starting at t1 (default = 0 for
                        beginning of recording)
        t2          scalar, retrieve data ending at t2 (default = 0 for end
                        of recording)
        channel     integer or array, choose a single channel or array of
                        channels to extract from sev data (default = 0 for
                        all channels)
        ranges      array of valid time range column vectors
        just_names  boolean, retrieve only the valid event names
        event_name  string, specific event name to retrieve data from
        verbose     boolean, set to false to disable console output
        fs          float, sampling rate override. Useful for lower
                        sampling rates that aren't correctly written into
                        the SEV header.
        scale       float, scale factor for exported streaming data. Default = 1.
    """


    data = tdt.StructType()
    sample_info = []

    if os.path.isfile(sev_dir):
        # treat as single file only
        sev_files = [sev_dir]
    elif os.path.isdir(sev_dir):
        # treat as directory
        sev_dir = os.path.join(sev_dir, "")
        sev_files = tdt.get_files(sev_dir, ".sev", ignore_mac=True)

        # parse log files
        if just_names == 0:
            txt_file_list = tdt.get_files(sev_dir, "_log.txt", ignore_mac=True)

            n_txtfiles = len(txt_file_list)
            if n_txtfiles < 1 and verbose:
                # fprintf('info: no log files in %s\n', SEV_DIR);
                pass
            else:
                start_search = re.compile("recording started at sample: (\d*)")
                gap_search = re.compile(
                    "gap detected. last saved sample: (\d*), new saved sample: (\d*)"
                )
                hour_search = re.compile("-(\d)h")
                for txt_path in txt_file_list:
                    # if verbose:
                    #     print("info: log file", txt_path)

                    # get store name
                    temp_sample_info = {"hour": 0}
                    temp_sample_info["name"] = os.path.split(txt_path)[-1][:4]
                    with open(txt_path, "r") as f:
                        log_text = f.read()
                        # if verbose:
                        #     print(log_text)

                    temp_start_sample = start_search.findall(log_text)
                    temp_sample_info["start_sample"] = int(temp_start_sample[0])
                    temp_hour = hour_search.findall(txt_path)
                    if len(temp_hour) > 0:
                        temp_sample_info["hour"] = int(temp_hour[-1])
                    if (
                        temp_sample_info["start_sample"] > 2
                        and temp_sample_info["hour"] == 0
                    ):
                        warnings.warn(
                            "{0} store starts on sample {1}".format(
                                temp_sample_info["name"],
                                temp_sample_info["start_sample"],
                            ),
                            Warning,
                            stacklevel=2,
                        )

                    # look for gap info
                    temp_sample_info["gaps"] = []
                    temp_sample_info["gap_text"] = ""
                    gap_text = gap_search.findall(log_text)
                    if len(gap_text):
                        temp_sample_info["gaps"] = np.array(gap_text, dtype=np.int64)
                        temp_sample_info["gap_text"] = "\n   ".join(
                            [x.group() for x in gap_search.finditer(log_text)]
                        )

                        if temp_sample_info["hour"] > 0:
                            warnings.warn(
                                "gaps detected in data set for {0}-{1}h!\n   {2}\nContact TDT for assistance.\n".format(
                                    temp_sample_info["name"],
                                    temp_sample_info["hour"],
                                    temp_sample_info["gap_text"],
                                ),
                                Warning,
                                stacklevel=2,
                            )
                        else:
                            warnings.warn(
                                "gaps detected in data set for {0}!\n   {1}\nContact TDT for assistance.\n".format(
                                    temp_sample_info["name"],
                                    temp_sample_info["gap_text"],
                                ),
                                Warning,
                                stacklevel=2,
                            )
                    sample_info.append(temp_sample_info)
    else:
        raise Exception("unable to find sev file or directory:\n\t" + sev_dir)

    nfiles = len(sev_files)
    if nfiles < 1:
        if just_names:
            return []
        # warnings.warn('no sev files found in {0}'.format(sev_dir), Warning, stacklevel=2)
        return None

    # if fs > 0:
    #     print("Using {:.4f} Hz as SEV sampling rate for {}".format(fs, event_name))

    file_list = []
    for file in sev_files:
        [filename, _] = os.path.splitext(file)
        [path, name] = os.path.split(filename)
        if name.startswith("._"):
            continue
        file_list.append({"fullname": file, "folder": path, "name": name})

    chan_search = re.compile("_[Cc]h([0-9]*)")
    hour_search = re.compile("-([0-9]*)h")
    name_search = re.compile("(?=_(.{4})_)")

    # find out what data we think is here
    for file in file_list:
        # find channel number
        match_result = chan_search.findall(file["name"])
        if match_result:
            file["chan"] = int(match_result[-1])
        else:
            file["chan"] = -1

        # find starting hour
        match_result = hour_search.findall(file["name"])
        if match_result:
            file["hour"] = int(match_result[-1])
        else:
            file["hour"] = 0

        # event name of stream
        matches = name_search.finditer(file["name"])
        match_result = [match.group(1) for match in matches]
        if match_result:
            file["event_name"] = match_result[-1]
        else:
            file["event_name"] = file["name"]

        # check file size
        file["data_size"] = os.stat(file["fullname"]).st_size - 40

        with open(file["fullname"], "rb") as sev:
            # create and fill stream_header struct
            stream_header = tdt.StructType()

            stream_header.size_bytes = np.fromfile(sev, dtype=np.uint64, count=1)[0]
            stream_header.file_type = np.fromfile(sev, dtype=np.uint8, count=3)
            stream_header.file_type = "".join(
                [chr(item) for item in stream_header.file_type]
            )
            stream_header.file_version = np.fromfile(sev, dtype=np.uint8, count=1)[0]
            stream_header.event_name = file["event_name"]

            if stream_header.file_version < 4:
                # prior to v3, OpenEx and RS4 were not setting this properly
                # (one of them was flipping it), so only trust the event name in
                # header if file_version is 3 or higher
                temp_event_name = np.fromfile(sev, dtype=np.uint8, count=4)
                temp_event_name = "".join([chr(item) for item in temp_event_name])
                if stream_header.file_version >= 3:
                    stream_header.event_name = temp_event_name

                # current channel of stream
                stream_header.channel_num = np.fromfile(sev, dtype=np.uint16, count=1)[
                    0
                ]
                file["chan"] = stream_header.channel_num
                # total number of channels in the stream
                stream_header.total_num_channels = np.fromfile(
                    sev, dtype=np.uint16, count=1
                )[0]
                # number of bytes per sample
                stream_header.sample_width_bytes = np.fromfile(
                    sev, dtype=np.uint16, count=1
                )[0]
                reserved = np.fromfile(sev, dtype=np.uint16, count=1)[0]

                # data format of stream in lower 3 bits
                data_format = np.fromfile(sev, dtype=np.uint8, count=1)[0]
                data_format &= 0b111
                stream_header.data_format = tdt.ALLOWED_FORMATS[data_format]

                # used to compute actual sampling rate
                stream_header.decimate = np.fromfile(sev, dtype=np.uint8, count=1)[0]
                stream_header.rate = np.fromfile(sev, dtype=np.uint16, count=1)[0]
            else:
                raise Exception(
                    "unknown version {0}".format(stream_header.file_version)
                )

            # compute sampling rate
            if stream_header.file_version > 0:
                stream_header.fs = (
                    np.power(2.0, (stream_header.rate - 12))
                    * 25000000
                    / stream_header.decimate
                )
            else:
                # make some assumptions if we don't have a real header
                stream_header.data_format = "single"
                stream_header.fs = 24414.0625
                stream_header.channel_num = file["chan"]
                warnings.warn(
                    """{0} has empty header;
assuming {1} ch {2} format {3}
upgrade to OpenEx v2.18 or above\n""".format(
                        file["name"],
                        stream_header.event_name,
                        stream_header.channel_num,
                        stream_header.data_format,
                    ),
                    Warning,
                    stacklevel=2,
                )

            if fs > 0:
                stream_header.fs = fs

            # add log info if it exists
            if just_names == 0:
                file["start_sample"] = 1
                file["gaps"] = []
                file["gap_text"] = ""
                for sss in sample_info:
                    if stream_header.event_name == sss["name"]:
                        if file["hour"] == sss["hour"]:
                            file["start_sample"] = sss["start_sample"]
                            file["gaps"] = sss["gaps"]
                            file["gap_text"] = sss["gap_text"]
            varname = tdt.fix_var_name(stream_header.event_name)
            file["itemsize"] = np.uint64(np.dtype(stream_header.data_format).itemsize)
            file["npts"] = file["data_size"] // file["itemsize"]
            file["fs"] = stream_header.fs
            file["data_format"] = stream_header.data_format
            file["event_name"] = stream_header.event_name
            file["varName"] = varname

    event_names = list(set([file["event_name"] for file in file_list]))
    if just_names:
        return event_names

    if t2 > 0:
        valid_time_range = np.array([[t1], [t2]])
    else:
        valid_time_range = np.array([[t1], [np.inf]])

    try:
        len(ranges)
        valid_time_range = ranges
    except:
        pass

    num_ranges = valid_time_range.shape[1]

    if num_ranges > 0:
        data["time_ranges"] = valid_time_range

    for this_event in event_names:
        if event_name and event_name != this_event:
            continue

        # get files for this event only
        file_list_temp = [
            file for file in file_list if file["event_name"] == this_event
        ]

        # extract header info
        fs = file_list_temp[0]["fs"]
        temp_event_name = file_list_temp[0]["event_name"]
        data_format = file_list_temp[0]["data_format"]

        chans = [f["chan"] for f in file_list_temp]
        hours = [f["hour"] for f in file_list_temp]
        max_chan = np.max(chans)
        min_chan = np.min(chans)
        max_hour = np.max(hours)
        hour_values = sorted(list(set(hours)))

        # preallocate data array
        # make channel filter a list
        if type(channel) is not list:
            channels = [channel]
        else:
            channels = channel
        if 0 in channels:
            channels = chans
        channels = sorted(list(set(channels)))

        for ch in channels:
            try:
                chans.index(ch)
                search_ch = ch
            except:
                warnings.warn(
                    "channel {0} not found in {1} event".format(ch, temp_event_name),
                    Warning,
                    stacklevel=2,
                )
                continue
        search_ch = min_chan

        # determine total samples if there is chunking, and how many samples are in each file
        total_samples = 0
        total_samples_exp = 0  # expected, if gaps are accounted for
        npts = [
            np.uint64(0) for i in hour_values
        ]  # number actually in the file, if gaps
        nexp = np.zeros(len(hour_values))  # number we expected without gaps
        for jjj in hour_values:
            ind1 = np.asarray(hours) == jjj
            ind2 = np.asarray(chans) == search_ch
            temp_num = np.where(ind1 & ind2)[0]
            if len(temp_num) < 1:
                raise Exception(
                    "matching file not found for hour {0} channel {1}".format(
                        jjj, search_ch
                    )
                )
            elif len(temp_num) > 1:
                raise Exception(
                    "too many matches found for hour {0} channel {1}".format(
                        jjj, search_ch
                    )
                )
            temp_num = temp_num[0]

            # actual samples
            npts[jjj] = np.uint64(file_list_temp[temp_num]["npts"])
            total_samples = total_samples + npts[jjj]

            # expected samples
            total_samples_exp = file_list_temp[temp_num]["start_sample"]
            missing = np.sum(np.diff(file_list_temp[temp_num]["gaps"]))
            nexp[jjj] = npts[jjj] + missing
            total_samples_exp = total_samples_exp + nexp[jjj]

        # if we are doing time filtering, determine which files we need to read
        # from and how many samples
        absolute_start_sample = np.zeros(num_ranges, dtype=np.uint64)
        absolute_end_sample = np.zeros(num_ranges, dtype=np.uint64)
        start_hour_file = np.zeros(num_ranges, dtype=np.uint64)
        end_hour_file = np.zeros(num_ranges, dtype=np.uint64)
        start_hour_samples_to_skip = np.zeros(num_ranges, dtype=np.uint64)
        end_hour_samples_end = np.zeros(num_ranges, dtype=np.uint64)

        for jj in range(num_ranges):
            # find recording start sample
            this_start_sample = file_list_temp[temp_num]["start_sample"] - 1
            minSample = time2sample(valid_time_range[0, jj], fs, t1=True)
            absolute_start_sample[jj] = np.max(minSample, 0) + 1
            if np.isinf(valid_time_range[1, jj]):
                absolute_end_sample[jj] = total_samples
            else:
                maxSample = time2sample(valid_time_range[1, jj], fs, t2=True)
                absolute_end_sample[jj] = np.minimum(
                    np.max(maxSample, 0), total_samples
                )
            curr_samples = 0
            for jjj in hour_values:
                if curr_samples <= absolute_start_sample[jj]:
                    start_hour_samples_to_skip[jj] = (
                        absolute_start_sample[jj] - curr_samples - 1
                    )
                    start_hour_file[jj] = jjj
                if curr_samples + npts[jjj] >= absolute_end_sample[jj]:
                    end_hour_samples_end[jj] = absolute_end_sample[jj] - curr_samples
                    end_hour_file[jj] = jjj
                    break
                curr_samples = curr_samples + npts[jjj]

        # now allocate it
        varname = file_list_temp[0]["varName"]
        data[varname] = tdt.StructType()
        data[varname]["channels"] = channels

        # preallocate
        if np.any([fff["gap_text"] != "" for fff in file_list_temp]):
            data[varname].data = []
            data[varname]["name"] = varname
            data[varname]["fs"] = fs
            return data
        else:
            data[varname].data = [[] for i in range(num_ranges)]
            for jj in range(num_ranges):
                data[varname]["data"][jj] = np.zeros(
                    (
                        len(channels),
                        absolute_end_sample[jj]
                        - absolute_start_sample[jj]
                        + np.uint64(2 + this_start_sample),
                    ),
                    dtype=data_format,
                )

        # loop through the time ranges
        for ii in range(num_ranges):
            # loop through the channels
            arr_index = 0
            for chan in channels:
                chan_index = np.uint64(0) + this_start_sample

                ind2 = np.asarray(chans) == chan

                # loop through the chunks
                for kk in range(
                    start_hour_file[ii], end_hour_file[ii] + np.uint64(1)
                ):
                    ind1 = np.asarray(hours) == kk
                    if ~np.any(ind1 & ind2):
                        continue
                    file_num = np.where(ind1 & ind2)[0][0]

                    # read rest of file into data array as correct format
                    data[varname]["name"] = temp_event_name
                    data[varname]["fs"] = fs

                    # skip data load if there are gaps
                    if file_list_temp[file_num]["gap_text"] != "":
                        return data

                    # open file
                    with open(file_list_temp[file_num]["fullname"], "rb") as f:
                        # skip first 40 bytes from header
                        f.seek(40, os.SEEK_SET)

                        if kk == start_hour_file[ii]:
                            firstSample = start_hour_samples_to_skip[ii]
                        else:
                            firstSample = 0

                        if kk == end_hour_file[ii]:
                            lastSample = end_hour_samples_end[ii]
                        else:
                            lastSample = MAX_UINT64

                        # skip ahead
                        if firstSample > 0:
                            f.seek(
                                int(
                                    firstSample
                                    * file_list_temp[file_num]["itemsize"]
                                ),
                                os.SEEK_CUR,
                            )

                        if lastSample == MAX_UINT64:
                            ddd = np.frombuffer(f.read(), dtype=data_format)
                        else:
                            ddd = np.frombuffer(
                                f.read(
                                    int(
                                        (lastSample - firstSample + 1)
                                        * file_list_temp[file_num]["itemsize"]
                                    )
                                ),
                                dtype=data_format,
                            )
                            data[varname].data[ii][
                                arr_index,
                                int(chan_index) : (int(chan_index + len(ddd))),
                            ] = ddd
                            arr_index += 1
                            chan_index += len(ddd)

                        # if verbose:
                        #    print(file_list[file_num])
        
    return data


def header_to_text(header, scale):
    hhh = []
    hhh.append("Path:\t" + header.tev_path)
    hhh.append("Start:\t" + str(header.start_time[0]))
    hhh.append("Stop:\t" + str(header.stop_time[0]))
    hhh.append("ScaleFactor:\t{0}".format(scale))
    hhh.append("Stores:")
    for k in header.stores.keys():
        type_str = header.stores[k].type_str
        hhh.append("\tName:\t" + header.stores[k].name)
        hhh.append("\tType:\t" + header.stores[k].type_str)
        if type_str in ["streams", "snips"]:
            hhh.append("\tFreq:\t" + str(header.stores[k].fs))
            hhh.append("\tNChan:\t" + str(int(max(header.stores[k].chan))))
        if type_str in ["snips"]:
            hhh.append("\tSort:\t" + header.stores[k].sortname)
        if type_str in ["scalars"]:
            hhh.append("\t\tNChan:\t" + str(int(max(header.stores[k].chan))))
        hhh.append("")
    return "\n".join(hhh)

# a type for evtypes which is a list of strings that can contain ['all', 'epocs', 'snips', 'streams', or 'scalars'].
class EvType(StrEnum):
    ALL = "all"
    EPOCS = "epocs"
    SNIPS = "snips"
    STREAMS = "streams"
    SCALARS = "scalars"


def read_block(
    block_path,
    *,
    bitwise="",
    channel=0,
    combine=None,
    headers=0,
    nodata=False,
    ranges=None,
    store="",
    t1: int =0,
    t2: int =0,
    evtype: List[EvType] = [EvType.ALL],
    verbose=0,
    sortname="TankSort",
    export=None,
    scale=1,
    signal: ProgressSignals = None,
) -> Block:
    """TDT tank data extraction.

    data = read_block(block_path), where block_path is a string, retrieves
    all data from specified block directory in struct format. This reads
    the binary tank data and requires no Windows-based software.

    data.epocs      contains all epoc store data (onsets, offsets, values)
    data.snips      contains all snippet store data (timestamps, channels,
                    and raw data)
    data.streams    contains all continuous data (sampling rate and raw
                    data)
    data.scalars    contains all scalar data (samples and timestamps)
    data.info       contains additional information about the block

    optional keyword arguments:
        t1          scalar, retrieve data starting at t1 (default = 0 for
                        beginning of recording)
        t2          scalar, retrieve data ending at t2 (default = 0 for end
                        of recording)
        sortname    string, specify sort ID to use when extracting snippets
                        (default = 'TankSort')
        evtype      array of strings, specifies what type of data stores to
                        retrieve from the tank. Can contain 'all' (default),
                        'epocs', 'snips', 'streams', or 'scalars'.
                      example:
                          data = read_block(block_path, evtype=['epocs','snips'])
                              > returns only epocs and snips
        ranges      array of valid time range column vectors.
                      example:
                          tr = np.array([[1,3],[2,4]])
                          data = read_block(block_path, ranges=tr)
                              > returns only data on t=[1,2) and [3,4)
        nodata      boolean, only return timestamps, channels, and sort
                        codes for snippets, no waveform data (default = false).
                        Useful speed-up if not looking for waveforms
        store       string or list, specify a single store or array of stores
                        to extract.
        channel     integer or list, choose a single channel or array of channels
                        to extract from stream or snippet events. Default is 0,
                        to extract all channels.
        bitwise     string, specify an epoc store or scalar store that
                        contains individual bits packed into a 32-bit
                        integer. Onsets/offsets from individual bits will
                        be extracted.
        headers     var, set to 1 to return only the headers for this
                        block, so that you can make repeated calls to read
                        data without having to parse the TSQ file every
                        time, for faster consecutive reads. Once created,
                        pass in the headers using this parameter.
                      example:
                        heads = read_block(block_path, headers=1)
                        data = read_block(block_path, headers=heads, evtype=['snips'])
                        data = read_block(block_path, headers=heads, evtype=['streams'])
        combine     list, specify one or more data stores that were saved
                        by the Strobed Data Storage gizmo in Synapse (or an
                        Async_Stream_store macro in OpenEx). By default,
                        the data is stored in small chunks while the strobe
                        is high. This setting allows you to combine these
                        small chunks back into the full waveforms that were
                        recorded while the strobe was enabled.
                      example:
                        data = read_block(block_path, combine=['StS1'])
        export      string, choose a data exporting format.
                        csv:        data export to comma-separated value files
                                    streams: one file per store, one channel per column
                                    epocs: one column onsets, one column offsets
                        binary:     streaming data is exported as raw binary files
                                    one file per channel per store
                        interlaced: streaming data exported as raw binary files
                                    one file per store, data is interlaced
        scale       float, scale factor for exported streaming data. Default = 1.
        signal      a pyqt signal object, if specified, progress updates will be sent
    """

    if not hasattr(evtype, "__len__"):
        evtype = ["all"]

    try:
        evtype = [t.lower() for t in evtype]
    except:
        raise Exception("evtype must be a list of strings")

    if "all" in evtype:
        evtype = ["epocs", "snips", "streams", "scalars"]

    evtype = list(set(evtype))

    use_outside_headers = False
    do_headers_only = False
    if isinstance(headers, tdt.StructType) or isinstance(headers, dict):
        use_outside_headers = True
        header = headers
    else:
        header = tdt.StructType()
        if headers == 1:
            do_headers_only = True

    block_path = os.path.join(block_path, "")

    if not use_outside_headers:
        tsq_list = tdt.get_files(block_path, ".tsq", ignore_mac=True)

        if len(tsq_list) < 1:
            if not os.path.isdir(block_path):
                raise Exception("block path {0} not found".format(block_path))

            if "streams" in evtype:
                warnings.warn(
                    "no tsq file found, attempting to read sev files",
                    Warning,
                    stacklevel=2,
                )
                return read_sev(
                    block_path,
                    channel=channel,
                    event_name=store,
                    t1=t1,
                    t2=t2,
                    ranges=ranges,
                    verbose=verbose,
                    export=export,
                    scale=scale,
                )
            else:
                raise Exception("no TSQ file found in {0}".format(block_path))

        elif len(tsq_list) > 1:
            raise Exception("multiple TSQ files found\n{0}".format(",".join(tsq_list)))

        try:
            tsq = open(tsq_list[0], "rb")
        except:
            raise Exception("tsq file {0} could not be opened".format(tsq_list[0]))

        header.tev_path = tsq_list[0].replace(".tsq", ".tev")

    if not do_headers_only:
        try:
            tev = open(header.tev_path, "rb")
        except:
            raise Exception("tev file {0} could not be opened".format(header.tev_path))

    # look for epoch tagged notes
    tnt_path = header.tev_path.replace(".tev", ".tnt")
    note_str = np.array([])
    try:
        lines = np.array([line.rstrip("\n") for line in open(tnt_path)])
        # file version is in first line
        # note_file_version = lines[0]
        note_str = lines[1:]
    except:
        warnings.warn("tnt file could not be processed", Warning, stacklevel=2)

    # look for custom sort_ids
    custom_sort_event = []
    custom_sort_channel_map = []
    custom_sort_codes = []

    if "snips" in evtype and sortname != "TankSort":
        # we want a custom one, parse all custom sorts
        sort_ids = {"fileNames": [], "event": [], "sort_id": []}
        sort_path = os.path.join(block_path, "sort")

        try:
            for sort_id in os.listdir(sort_path):
                if os.path.isdir(os.path.join(sort_path, sort_id)):
                    # parse sort result file name
                    sort_files = tdt.get_files(
                        os.path.join(sort_path, sort_id), ".SortResult", ignore_mac=True
                    )
                    for sort_file in sort_files:
                        head, tail = os.path.split(sort_file)
                        sort_ids["event"].append(tail.split(".")[0])
                        sort_ids["fileNames"].append(sort_file)
                        sort_ids["sort_id"].append(os.path.split(head)[-1])

            # now look for the exact sortname specified by user
            if sortname in sort_ids["sort_id"]:
                for i in range(len(sort_ids["sort_id"])):
                    if sort_ids["sort_id"][i] == sortname:
                        # print(
                        #     "Using sort_id:{0} for event:{1}".format(
                        #         sortname, sort_ids["event"][i]
                        #     )
                        # )
                        custom_sort_event.append(sort_ids["event"][i])
                        ddd = np.fromfile(sort_ids["fileNames"][i], dtype=np.uint8)
                        custom_sort_channel_map.append(ddd[:1024])
                        custom_sort_codes.append(ddd[1024:])
            else:
                warnings.warn(
                    "sort_id:{0} not found\n".format(sortname), Warning, stacklevel=2
                )
        except:
            # no sort directory found
            pass

    """
    tbk file has block events information and on second time offsets
    to efficiently locate events if the data is queried by time.

    tsq file is a list of event headers, each 40 bytes long, ordered strictly
    by time.

    tev file contains event binary data

    tev and tsq files work together to get an event's data and attributes

    tdx file contains just information about epoc stores,
    is optionally generated after recording for fast retrieval
    of epoc information
    """

    # read TBK notes to get event info
    tbk_path = header.tev_path.replace(".tev", ".Tbk")
    block_notes = parse_tbk(tbk_path)

    if not use_outside_headers:
        # read start time
        tsq.seek(0, os.SEEK_SET)
        xxx = tsq.read(8)
        file_size = np.fromfile(tsq, dtype=np.int64, count=1)
        tsq.seek(48, os.SEEK_SET)
        code1 = np.fromfile(tsq, dtype=np.int32, count=1)
        assert code1 == tdt.EVMARK_STARTBLOCK, "Block start marker not found"
        tsq.seek(56, os.SEEK_SET)
        header.start_time = np.fromfile(tsq, dtype=np.float64, count=1)

        # read stop time
        tsq.seek(-32, os.SEEK_END)
        code2 = np.fromfile(tsq, dtype=np.int32, count=1)
        if code2 != tdt.EVMARK_STOPBLOCK:
            warnings.warn(
                "Block end marker not found, block did not end cleanly. Try setting T2 smaller if errors occur",
                Warning,
                stacklevel=2,
            )
            header.stop_time = np.nan
        else:
            tsq.seek(-24, os.SEEK_END)
            header.stop_time = np.fromfile(tsq, dtype=np.float64, count=1)

    data = tdt.StructType()
    data.epocs = tdt.StructType()
    data.snips = tdt.StructType()
    data.streams = tdt.StructType()
    data.scalars = tdt.StructType()
    data.info = tdt.StructType()

    # set info fields
    [data.info.tankpath, data.info.blockname] = os.path.split(
        os.path.normpath(block_path)
    )
    data.info.start_date = datetime.fromtimestamp(header.start_time[0])
    if not np.isnan(header.start_time):
        data.info.utc_start_time = data.info.start_date.strftime("%H:%M:%S")
    else:
        data.info.utc_start_time = np.nan

    if not np.isnan(header.stop_time):
        data.info.stop_date = datetime.fromtimestamp(header.stop_time[0])
        data.info.utc_stop_time = data.info.stop_date.strftime("%H:%M:%S")
    else:
        data.info.stop_date = np.nan
        data.info.utc_stop_time = np.nan

    if header.stop_time > 0:
        data.info.duration = (
            data.info.stop_date - data.info.start_date
        )  # datestr(s2-s1,'HH:MM:SS')
    data.info.stream_channel = channel
    data.info.snip_channel = channel

    # look for Synapse recording notes
    notes_txt_path = os.path.join(block_path, "Notes.txt")
    notes_txt_lines = []
    try:
        with open(notes_txt_path, "rt") as txt:
            notes_txt_lines = txt.readlines()
        # print("Found Synapse note file: {0}".format(notes_txt_path))
    except:
        # warnings.warn('Synapse Notes file could not be processed', Warning, stacklevel=2)
        pass

    note_text = []
    note_ts = []
    do_once = 1
    this_note_text = ""
    if len(notes_txt_lines) > 1:
        targets = ["Experiment", "Subject", "User", "Start", "Stop"]
        in_note = False
        for note_line in notes_txt_lines:
            note_line = note_line.strip()
            if len(note_line) == 0:
                continue

            target_found = False
            for target in targets:
                test_str = target + ":"
                eee = len(test_str)
                if len(note_line) >= eee + 2:
                    if note_line.startswith(test_str):
                        setattr(data.info, target.lower(), note_line[eee + 1 :])
                        target_found = True
                        break
            if target_found:
                continue

            if do_once:
                if "-" in data.info.start:
                    yearfmt = "%Y-%m-%d"
                else:
                    yearfmt = "%m/%d/%Y"
                if "m" in data.info.start.lower():
                    timefmt = "%I:%M:%S%p"
                else:
                    timefmt = "%H:%M:%S"
                rec_start = datetime.strptime(
                    data.info.start.lower(), timefmt + " " + yearfmt
                )
                curr_day = rec_start.day
                curr_month = rec_start.month
                curr_year = rec_start.year
                do_once = 0

            # look for actual notes
            test_str = "Note-"
            eee = len(test_str)
            note_start = False
            no_buttons = False
            if len(note_line) >= eee + 2:
                if note_line.startswith(test_str):
                    in_note = False
                    note_start = True
            if in_note:
                if '"' in note_line:
                    this_note_text += note_line.split('"')[0]
                    note_text.append(this_note_text)
                    in_note = False
                else:
                    this_note_text += "\n" + note_line
            if note_start:
                # start of new note
                this_note_text = ""
                try:
                    note_id = re.findall("(?<=\[)(.*?)(?=\s*\])", note_line)
                    if len(note_id):
                        note_id = note_id[0]
                    else:
                        no_buttons = True
                except:
                    note_id = re.findall(test_str + "(.*?)(?=\s*:)", note_line)[0]

                note_parts = note_line.split(" ")
                note_time = note_parts[1]
                note_dt = datetime.strptime(note_time.lower(), timefmt)
                note_dt = note_dt.replace(year=curr_year)
                note_dt = note_dt.replace(month=curr_month)
                note_dt = note_dt.replace(day=curr_day)

                note_time_relative = note_dt - rec_start
                date_changed = False
                if note_id == "none" or no_buttons:
                    quotes = note_line.split('"')
                    if len(quotes) <= 2:
                        in_note = True
                    this_note_text = quotes[1]

                    if "date changed to" in this_note_text:
                        date_changed = True
                        # print(quotes[1])
                        # print()
                        temp = datetime.strptime(this_note_text[16:].lower(), yearfmt)
                        curr_day = temp.day
                        curr_month = temp.month
                        curr_year = temp.year
                    if not in_note:
                        note_text.append(this_note_text)
                else:
                    note_text.append(note_id)
                if not date_changed:
                    note_ts.append(note_time_relative.seconds)

    note_text = np.array(note_text)

    epocs = tdt.StructType()
    epocs.name = []
    epocs.buddies = []
    epocs.ts = []
    epocs.code = []
    epocs.type = []
    epocs.type_str = []
    epocs.data = []
    epocs.dform = []

    notes = tdt.StructType()
    notes.name = []
    notes.index = []
    notes.ts = []

    """
    # TTank event header structure
    tsqEventHeader = struct(...
        'size', 0, ...
        'type', 0, ...  % (long) event type: snip, pdec, epoc etc
        'code', 0, ...  % (long) event name: must be 4 chars, cast as a long
        'channel', 0, ... % (unsigned short) data acquisition channel
        'sortcode', 0, ... % (unsigned short) sort code for snip data. See also OpenSorter .SortResult file.
        'timestamp', 0, ... % (double) time offset when even occurred
        'ev_offset', 0, ... % (int64) data offset in the TEV file OR (double) strobe data value
        'format', 0, ... % (long) data format of event: byte, short, float (typical), or double
        'frequency', 0 ... % (float) sampling frequency
    );
    """

    if not use_outside_headers:
        tsq.seek(40, os.SEEK_SET)

        if t2 > 0:
            # make the reads shorter if we are stopping early
            read_size = 10000000
        else:
            read_size = 50000000

        # map store code to other info
        header.stores = tdt.StructType()
        code_ct = 0
        while True:
            # read all headers into one giant array
            heads = np.frombuffer(tsq.read(read_size * 4), dtype=np.uint32)
            if len(heads) == 0:
                continue

            rem = len(heads) % 10
            if rem != 0:
                warnings.warn(
                    "Block did not end cleanly, removing last {0} headers".format(rem),
                    Warning,
                    stacklevel=2,
                )
                heads = heads[:-rem]

            # reshape so each column is one header
            heads = heads.reshape((-1, 10)).T

            # check the codes first and build store maps and note arrays
            codes = heads[2, :]

            good_codes = codes > 0
            bad_codes = np.logical_not(good_codes)

            if np.sum(bad_codes) > 0:
                warnings.warn(
                    "Bad TSQ headers were written, removing {0}, keeping {1} headers".format(
                        sum(bad_codes), sum(good_codes)
                    ),
                    Warning,
                    stacklevel=2,
                )
                heads = heads[:, good_codes]
                codes = heads[2, :]

            # get set of codes but preserve order in the block
            store_codes = []
            unique_codes, unique_ind = np.unique(codes, return_index=True)
            for counter, x in enumerate(unique_codes):
                store_codes.append(
                    {
                        "code": x,
                        "type": heads[1, unique_ind[counter]],
                        "type_str": code_to_type(heads[1, unique_ind[counter]]),
                        "ucf": check_ucf(heads[1, unique_ind[counter]]),
                        "epoc_type": epoc_to_type(heads[1, unique_ind[counter]]),
                        "dform": heads[8, unique_ind[counter]],
                        "size": heads[0, unique_ind[counter]],
                        "buddy": heads[3, unique_ind[counter]],
                        "temp": heads[:, unique_ind[counter]],
                    }
                )

            for store_code in store_codes:
                if store_code["code"] in [tdt.EVMARK_STARTBLOCK, tdt.EVMARK_STOPBLOCK]:
                    continue
                if store_code["code"] == 0:
                    warnings.warn(
                        "Skipping unknown header code 0", Warning, stacklevel=2
                    )
                    continue

                store_code["name"] = code_to_name(store_code["code"])

                skip_disabled = 0
                if len(block_notes) > 0:
                    for temp in block_notes:
                        if temp.StoreName == store_code["name"]:
                            if "Enabled" in temp.keys():
                                if temp.Enabled == "2":
                                    warnings.warn(
                                        "{0} store DISABLED".format(temp.StoreName),
                                        Warning,
                                        stacklevel=2,
                                    )
                                    skip_disabled = 1
                                    break

                if skip_disabled:
                    continue

                # if looking for a particular store and this isn't it, flag it
                # for now. need to keep looking for buddy epocs
                skip_by_name = False
                if store:
                    if isinstance(store, str):
                        if store != store_code["name"]:
                            skip_by_name = True
                    elif isinstance(store, list):
                        if store_code["name"] not in store:
                            skip_by_name = True

                store_code["var_name"] = tdt.fix_var_name(store_code["name"], verbose)

                # shorthand
                var_name = store_code["var_name"]

                # do store type filter here
                if store_code["type_str"] not in evtype:
                    continue

                if store_code["type_str"] == "epocs":
                    buddy = "".join(
                        [
                            str(chr(c))
                            for c in np.array([store_code["buddy"]]).view(np.uint8)
                        ]
                    )
                    buddy = buddy.replace("\x00", " ")
                    if skip_by_name:
                        if store:
                            if isinstance(store, str):
                                if buddy == store:
                                    skip_by_name = False
                            elif isinstance(store, list):
                                if buddy in store:
                                    skip_by_name = False
                    if not store_code["name"] in epocs.name:
                        if skip_by_name:
                            continue
                        epocs.name.append(store_code["name"])
                        epocs.buddies.append(buddy)
                        epocs.code.append(store_code["code"])
                        epocs.ts.append([])
                        epocs.type.append(store_code["epoc_type"])
                        epocs.type_str.append(store_code["type_str"])
                        epocs.data.append([])
                        epocs.dform.append(store_code["dform"])

                # skip other types of stores
                if skip_by_name:
                    continue

                # add store information to store map
                if not var_name in header.stores.keys():
                    if store_code["type_str"] != "epocs":
                        header.stores[var_name] = tdt.StructType(
                            name=store_code["name"],
                            code=store_code["code"],
                            size=store_code["size"],
                            type=store_code["type"],
                            type_str=store_code["type_str"],
                        )
                        if header.stores[var_name].type_str == "streams":
                            header.stores[var_name].ucf = store_code["ucf"]
                        if header.stores[var_name].type_str != "scalars":
                            header.stores[var_name].fs = np.double(
                                np.array([store_code["temp"][9]]).view(np.float32)[0]
                            )

                        header.stores[var_name].dform = store_code["dform"]

                valid_ind = np.where(codes == store_code["code"])[0]

                # look for notes in 'freqs' field for epoch or scalar events
                if len(note_str) > 0 and store_code["type_str"] in ["scalars", "epocs"]:
                    # find all possible notes for this store
                    user_notes = heads[9, valid_ind].view(np.uint32)

                    # find only where note field is non-zero and extract those
                    note_index = user_notes != 0
                    if np.any(note_index):
                        if not store_code["name"] in notes.name:
                            notes.name.append(store_code["name"])
                            notes.ts.append([])
                            notes.index.append([])
                        ts_ind = valid_ind[note_index]

                        note_ts = (
                            np.reshape(heads[[[4], [5]], ts_ind].T, (-1, 1)).T.view(
                                np.float64
                            )
                            - header.start_time
                        )
                        # round timestamps to the nearest sample
                        note_ts = time2sample(note_ts, to_time=True)
                        note_index = user_notes[note_index]
                        try:
                            loc = notes.name.index(store_code["name"])
                            notes.ts[loc].extend(note_ts)
                            notes.index[loc].extend(note_index)
                        except:
                            pass

                temp = heads[3, valid_ind].view(np.uint16)
                if store_code["type_str"] != "epocs":
                    if not hasattr(header.stores[var_name], "ts"):
                        header.stores[var_name].ts = []
                    vvv = (
                        np.reshape(heads[[[4], [5]], valid_ind].T, (-1, 1)).T.view(
                            np.float64
                        )
                        - header.start_time
                    )
                    # round timestamps to the nearest sample
                    vvv = time2sample(vvv, to_time=True)
                    header.stores[var_name].ts.append(vvv)
                    if (not nodata) or (store_code["type_str"] == "streams"):
                        if not hasattr(header.stores[var_name], "data"):
                            header.stores[var_name].data = []
                        header.stores[var_name].data.append(
                            np.reshape(heads[[[6], [7]], valid_ind].T, (-1, 1)).T.view(
                                np.float64
                            )
                        )
                    if not hasattr(header.stores[var_name], "chan"):
                        header.stores[var_name].chan = []
                    header.stores[var_name].chan.append(temp[::2])

                    if store_code["type_str"] == "snips":
                        if "sortcode" not in header.stores[var_name].keys():
                            header.stores[var_name].sortcode = []
                        if len(custom_sort_codes) > 0 and var_name in custom_sort_event:
                            # apply custom sort codes
                            for tempp in range(len(custom_sort_event)):
                                if (
                                    type(custom_sort_codes[tempp]) == np.ndarray
                                    and header.stores[var_name].name
                                    == custom_sort_event[tempp]
                                ):
                                    sortchannels = np.where(
                                        custom_sort_channel_map[tempp]
                                    )[0]
                                    header.stores[var_name].sortcode.append(
                                        custom_sort_codes[tempp][valid_ind + code_ct]
                                    )
                                    code_ct += len(codes)
                                    header.stores[var_name].sortname = sortname
                                    header.stores[var_name].sortchannels = sortchannels
                                elif (
                                    type(custom_sort_codes[tempp]) != np.ndarray
                                    and header.stores[var_name].name
                                    == custom_sort_event[tempp]
                                ):
                                    header.stores[var_name].sortcode.append(temp[1::2])
                                    header.stores[var_name].sortname = "TankSort"
                                else:
                                    continue
                        else:
                            header.stores[var_name].sortcode.append(temp[1::2])
                            header.stores[var_name].sortname = "TankSort"
                else:
                    loc = epocs.name.index(store_code["name"])
                    # round timestamps to the nearest sample
                    vvv = (
                        np.reshape(heads[[[4], [5]], valid_ind].T, (-1, 1)).T.view(
                            np.float64
                        )
                        - header.start_time
                    )
                    # round timestamps to the nearest sample
                    vvv = time2sample(vvv, to_time=True)
                    epocs.ts[loc] = np.append(epocs.ts[loc], vvv)
                    epocs.data[loc] = np.append(
                        epocs.data[loc],
                        np.reshape(heads[[[6], [7]], valid_ind].T, (-1, 1)).T.view(
                            np.float64
                        ),
                    )
                del temp
            del codes

            last_ts = heads[[4, 5], -1].view(np.float64) - header.start_time
            last_ts = last_ts[0]

            # break early if time filter
            if t2 > 0 and last_ts > t2:
                break

            # eof reached
            if heads.size < read_size:
                break

        if t2 > 0:
            lastRead = t2
        else:
            lastRead = last_ts

        # make fake Note epoc if it doesn't exist already
        if len(note_text) > 0 and "Note" not in epocs.name:
            epocs.name.append("Note")
            epocs.buddies.append("    ")
            epocs.code.append(
                np.array([ord(x) for x in "Note"], dtype=np.uint8).view(np.uint32)[0]
            )
            epocs.ts.append(np.array(note_ts, dtype=np.float64))
            epocs.type.append("onset")
            epocs.type_str.append("epocs")
            epocs.typeNum = 2
            epocs.data.append(np.arange(1, len(note_ts) + 1))
            epocs.dform.append(4)

        # put epocs into header
        for ii in range(len(epocs.name)):
            # find all non-buddies first
            if epocs.type[ii] == "onset":
                var_name = tdt.fix_var_name(epocs.name[ii])
                header.stores[var_name] = tdt.StructType()
                header.stores[var_name].name = epocs.name[ii]
                ts = epocs.ts[ii]
                header.stores[var_name].onset = ts
                header.stores[var_name].offset = np.append(ts[1:], np.inf)
                header.stores[var_name].type = epocs.type[ii]
                header.stores[var_name].type_str = epocs.type_str[ii]
                header.stores[var_name].data = epocs.data[ii]
                header.stores[var_name].dform = epocs.dform[ii]
                header.stores[var_name].size = 10

        # add all buddy epocs
        for ii in range(len(epocs.name)):
            if epocs.type[ii] == "offset":
                var_name = tdt.fix_var_name(epocs.buddies[ii])
                if var_name not in header.stores.keys():
                    warnings.warn(
                        epocs.buddies[ii] + " buddy epoc not found, skipping", Warning
                    )
                    continue

                header.stores[var_name].offset = epocs.ts[ii]

                # handle odd case where there is a single offset event and no onset events
                if "onset" not in header.stores[var_name].keys():
                    header.stores[var_name].name = epocs.buddies[ii]
                    header.stores[var_name].onset = 0
                    header.stores[var_name].type_str = "epocs"
                    header.stores[var_name].type = "onset"
                    header.stores[var_name].data = 0
                    header.stores[var_name].dform = 4
                    header.stores[var_name].size = 10

                # fix time ranges
                if header.stores[var_name].offset[0] < header.stores[var_name].onset[0]:
                    header.stores[var_name].onset = np.append(
                        0, header.stores[var_name].onset
                    )
                    header.stores[var_name].data = np.append(
                        header.stores[var_name].data[0], header.stores[var_name].data
                    )
                if (
                    header.stores[var_name].onset[-1]
                    > header.stores[var_name].offset[-1]
                ):
                    header.stores[var_name].offset = np.append(
                        header.stores[var_name].offset, np.inf
                    )

        # fix secondary epoc offsets
        if len(block_notes) > 0:
            for ii in range(len(epocs.name)):
                if epocs.type[ii] == "onset":
                    current_name = epocs.name[ii]
                    var_name = tdt.fix_var_name(epocs.name[ii])
                    for storeNote in block_notes:
                        if storeNote["StoreName"] == header.stores[var_name].name:
                            head_name = storeNote["HeadName"]
                            if "|" in head_name:
                                primary = tdt.fix_var_name(head_name[-4:])
                                if primary in header.stores.keys():
                                    header.stores[var_name].offset = header.stores[
                                        primary
                                    ].offset

        del epocs

        # if there is a custom sort name but this store ID isn't included, ignore it altogether
        keys = header.stores.keys()
        for var_name in keys:
            if header.stores[var_name].type_str == "snips":
                if "snips" in evtype and sortname != "TankSort":
                    if "sortcode" not in header.stores[var_name].keys():
                        header.stores.pop(var_name)

        for var_name in header.stores.keys():
            # convert cell arrays to regular arrays
            if "ts" in header.stores[var_name].keys():
                header.stores[var_name].ts = np.concatenate(
                    header.stores[var_name].ts, axis=1
                )[0]
            if "chan" in header.stores[var_name].keys():
                header.stores[var_name].chan = np.concatenate(
                    header.stores[var_name].chan
                )
            if "sortcode" in header.stores[var_name].keys():
                header.stores[var_name].sortcode = np.concatenate(
                    header.stores[var_name].sortcode
                )
            if "data" in header.stores[var_name].keys():
                if header.stores[var_name].type_str != "epocs":
                    header.stores[var_name].data = np.concatenate(
                        header.stores[var_name].data, axis=1
                    )[0]

            # if it's a data type, cast as a file offset pointer instead of data
            if header.stores[var_name].type_str in ["streams", "snips"]:
                if "data" in header.stores[var_name].keys():
                    header.stores[var_name].data = header.stores[var_name].data.view(
                        np.uint64
                    )
            if "chan" in header.stores[var_name].keys():
                if np.max(header.stores[var_name].chan) == 1:
                    header.stores[var_name].chan = [1]
        del heads  # don't need this anymore

    if do_headers_only:
        try:
            tsq.close()
        except:
            pass
        return header

    if t2 > 0:
        valid_time_range = np.array([[t1], [t2]])
    else:
        valid_time_range = np.array([[t1], [np.inf]])

    if hasattr(ranges, "__len__"):
        valid_time_range = ranges

    num_ranges = valid_time_range.shape[1]
    if num_ranges > 0:
        data.time_ranges = valid_time_range

    # loop through all possible stores and do full time filter
    for var_name in header.stores.keys():
        current_type_str = header.stores[var_name].type_str

        if current_type_str not in evtype:
            continue

        # don't modify header if it came from outside
        if use_outside_headers:
            data[current_type_str][var_name] = copy.deepcopy(header.stores[var_name])
        else:
            data[current_type_str][var_name] = header.stores[var_name]

        firstStart = valid_time_range[0, 0]
        last_stop = valid_time_range[1, -1]

        if "ts" in header.stores[var_name].keys():
            if current_type_str == "streams":
                data[current_type_str][var_name].start_time = [
                    0 for jj in range(num_ranges)
                ]
            else:
                this_dtype = data[current_type_str][var_name].ts.dtype
                data[current_type_str][var_name].filtered_ts = [
                    np.array([], dtype=this_dtype) for jj in range(num_ranges)
                ]
            if hasattr(data[current_type_str][var_name], "chan"):
                data[current_type_str][var_name].filtered_chan = [
                    [] for jj in range(num_ranges)
                ]
            if hasattr(data[current_type_str][var_name], "sortcode"):
                this_dtype = data[current_type_str][var_name].sortcode.dtype
                data[current_type_str][var_name].filtered_sort_code = [
                    np.array([], dtype=this_dtype) for jj in range(num_ranges)
                ]
            if hasattr(data[current_type_str][var_name], "data"):
                this_dtype = data[current_type_str][var_name].data.dtype
                data[current_type_str][var_name].filtered_data = [
                    np.array([], dtype=this_dtype) for jj in range(num_ranges)
                ]

            filter_ind = [[] for i in range(num_ranges)]
            for jj in range(num_ranges):
                start = valid_time_range[0, jj]
                stop = valid_time_range[1, jj]
                ind1 = data[current_type_str][var_name].ts >= start
                ind2 = data[current_type_str][var_name].ts < stop
                filter_ind[jj] = np.where(ind1 & ind2)[0]
                bSkip = 0
                if len(filter_ind[jj]) == 0:
                    # if it's a stream and a short window, we might have missed it
                    if current_type_str == "streams":
                        ind2 = np.where(ind2)[0]
                        if len(ind2) > 0:
                            ind2 = ind2[-1]
                            # keep one prior for streams (for all channels)
                            nchan = max(data[current_type_str][var_name].chan)
                            if ind2 - nchan >= -1:
                                filter_ind[jj] = ind2 - np.arange(nchan - 1, -1, -1)
                                temp = data[current_type_str][var_name].ts[
                                    filter_ind[jj]
                                ]
                                data[current_type_str][var_name].start_time[jj] = temp[
                                    0
                                ]
                                bSkip = 1

                if len(filter_ind[jj]) > 0:
                    # parse out the information we need
                    if current_type_str == "streams":
                        # keep one prior for streams (for all channels)
                        if not bSkip:
                            nchan = max(data[current_type_str][var_name].chan)
                            temp = filter_ind[jj]
                            if temp[0] - nchan > -1:
                                filter_ind[jj] = np.concatenate(
                                    [-np.arange(nchan, 0, -1) + temp[0], filter_ind[jj]]
                                )
                            temp = data[current_type_str][var_name].ts[filter_ind[jj]]
                            data[current_type_str][var_name].start_time[jj] = temp[0]
                    else:
                        data[current_type_str][var_name].filtered_ts[jj] = data[
                            current_type_str
                        ][var_name].ts[filter_ind[jj]]

                    if hasattr(data[current_type_str][var_name], "chan"):
                        if len(data[current_type_str][var_name].chan) > 1:
                            data[current_type_str][var_name].filtered_chan[jj] = data[
                                current_type_str
                            ][var_name].chan[filter_ind[jj]]
                        else:
                            data[current_type_str][var_name].filtered_chan[jj] = data[
                                current_type_str
                            ][var_name].chan
                    if hasattr(data[current_type_str][var_name], "sortcode"):
                        data[current_type_str][var_name].filtered_sort_code[jj] = data[
                            current_type_str
                        ][var_name].sortcode[filter_ind[jj]]
                    if hasattr(data[current_type_str][var_name], "data"):
                        data[current_type_str][var_name].filtered_data[jj] = data[
                            current_type_str
                        ][var_name].data[filter_ind[jj]]

            if current_type_str == "streams":
                delattr(data[current_type_str][var_name], "ts")
                delattr(data[current_type_str][var_name], "data")
                delattr(data[current_type_str][var_name], "chan")
                if not hasattr(data[current_type_str][var_name], "filtered_chan"):
                    data[current_type_str][var_name].filtered_chan = [
                        [] for i in range(num_ranges)
                    ]
                if not hasattr(data[current_type_str][var_name], "filtered_data"):
                    data[current_type_str][var_name].filtered_data = [
                        [] for i in range(num_ranges)
                    ]
                if not hasattr(data[current_type_str][var_name], "start_time"):
                    data[current_type_str][var_name].start_time = -1
            else:
                # consolidate other fields
                if hasattr(data[current_type_str][var_name], "filtered_ts"):
                    data[current_type_str][var_name].ts = np.concatenate(
                        data[current_type_str][var_name].filtered_ts
                    )
                    delattr(data[current_type_str][var_name], "filtered_ts")
                else:
                    data[current_type_str][var_name].ts = []
                if hasattr(data[current_type_str][var_name], "chan"):
                    if hasattr(data[current_type_str][var_name], "filtered_chan"):
                        data[current_type_str][var_name].chan = np.concatenate(
                            data[current_type_str][var_name].filtered_chan
                        )
                        delattr(data[current_type_str][var_name], "filtered_chan")
                        if current_type_str == "snips":
                            if len(set(data[current_type_str][var_name].chan)) == 1:
                                data[current_type_str][var_name].chan = [
                                    data[current_type_str][var_name].chan[0]
                                ]

                    else:
                        data[current_type_str][var_name].chan = []
                if hasattr(data[current_type_str][var_name], "sortcode"):
                    if hasattr(data[current_type_str][var_name], "filtered_sort_code"):
                        data[current_type_str][var_name].sortcode = np.concatenate(
                            data[current_type_str][var_name].filtered_sort_code
                        )
                        delattr(data[current_type_str][var_name], "filtered_sort_code")
                    else:
                        data[current_type_str][var_name].sortcode = []
                if hasattr(data[current_type_str][var_name], "data"):
                    if hasattr(data[current_type_str][var_name], "filtered_data"):
                        data[current_type_str][var_name].data = np.concatenate(
                            data[current_type_str][var_name].filtered_data
                        )
                        delattr(data[current_type_str][var_name], "filtered_data")
                    else:
                        data[current_type_str][var_name].data = []
        else:
            # handle epoc events
            filter_ind = []
            for jj in range(num_ranges):
                start = valid_time_range[0, jj]
                stop = valid_time_range[1, jj]
                ind1 = data[current_type_str][var_name].onset >= start
                ind2 = data[current_type_str][var_name].onset < stop
                filter_ind.append(np.where(ind1 & ind2)[0])

            filter_ind = np.concatenate(filter_ind)
            if len(filter_ind) > 0:
                data[current_type_str][var_name].onset = data[current_type_str][
                    var_name
                ].onset[filter_ind]
                data[current_type_str][var_name].data = data[current_type_str][
                    var_name
                ].data[filter_ind]
                data[current_type_str][var_name].offset = data[current_type_str][
                    var_name
                ].offset[filter_ind]
                if var_name == "Note":
                    try:
                        data[current_type_str][var_name].notes = note_text[filter_ind]
                    except:
                        warnings.warn(
                            "Problem with Notes.txt file", Warning, stacklevel=2
                        )
                        data[current_type_str][var_name].notes = []
                # fix time ranges
                if (
                    data[current_type_str][var_name].offset[0]
                    < data[current_type_str][var_name].onset[0]
                ):
                    if data[current_type_str][var_name].onset[0] > firstStart:
                        data[current_type_str][var_name].onset = np.concatenate(
                            [[firstStart], data[current_type_str][var_name].onset]
                        )
                if data[current_type_str][var_name].offset[-1] > last_stop:
                    data[current_type_str][var_name].offset[-1] = last_stop
            else:
                # default case is no valid events for this store
                data[current_type_str][var_name].onset = []
                data[current_type_str][var_name].data = []
                data[current_type_str][var_name].offset = []
                if var_name == "Note":
                    data[current_type_str][var_name].notes = []

        # see if there are any notes to add
        if hasattr(header.stores, var_name):
            try:
                loc = notes.name.index(data[current_type_str][var_name].name)
                data[current_type_str][var_name].notes = tdt.StructType()
                ts = notes.ts[loc][0]
                note_index = np.array(notes.index[loc])
                ind1 = ts >= firstStart
                ind2 = ts < last_stop
                valid_ind = np.where(ind1 & ind2)[0]
                data[current_type_str][var_name].notes.ts = ts[valid_ind]
                data[current_type_str][var_name].notes.index = note_index[valid_ind]
                data[current_type_str][var_name].notes.notes = note_str[
                    note_index[valid_ind] - 1
                ]  # zero-based indexing
            except:
                pass

    # see which stores might be in SEV files
    sev_names = read_sev(block_path, just_names=True)
    signal.max = len(header.stores.keys())

    signal.started.emit()
    i = 0
    for current_name in header.stores.keys():
        i += 1
        # emit the percentage through the loop
        signal.progress.emit(int(100 * i / signal.max))
        current_type_str = header.stores[current_name].type_str
        if current_type_str not in evtype:
            continue

        current_size = data[current_type_str][current_name].size
        current_type_str = data[current_type_str][current_name].type_str
        current_data_format = tdt.ALLOWED_FORMATS[
            data[current_type_str][current_name].dform
        ]
        if hasattr(data[current_type_str][current_name], "fs"):
            current_freq = data[current_type_str][current_name].fs
        sz = np.uint64(np.dtype(current_data_format).itemsize)

        # load data struct based on the type
        if current_type_str == "epocs":
            pass
        elif current_type_str == "scalars":
            if len(data[current_type_str][current_name].chan) > 0:
                nchan = int(np.max(data[current_type_str][current_name].chan))
            else:
                nchan = 0
            if nchan > 1:
                # organize data by sample
                # find channels with most and least amount of data
                ind = []
                min_length = np.inf
                max_length = 0
                for xx in range(nchan):
                    ind.append(
                        np.where(data[current_type_str][current_name].chan == xx + 1)[0]
                    )
                    min_length = min(len(ind[-1]), min_length)
                    max_length = max(len(ind[-1]), max_length)
                if min_length != max_length:
                    warnings.warn(
                        "Truncating store {0} to {1} values (from {2})".format(
                            current_name, min_length, max_length
                        ),
                        Warning,
                    )
                    ind = [ind[xx][:min_length] for xx in range(nchan)]
                if not nodata:
                    data[current_type_str][current_name].data = (
                        data[current_type_str][current_name]
                        .data[np.concatenate(ind)]
                        .reshape(nchan, -1)
                    )

                # only use timestamps from first channel
                data[current_type_str][current_name].ts = data[current_type_str][
                    current_name
                ].ts[ind[0]]

                # remove channels field
                delattr(data[current_type_str][current_name], "chan")
            if (
                hasattr(data[current_type_str][current_name], "notes")
                and current_name != "Note"
            ):
                data[current_type_str][current_name].notes.notes = (
                    data[current_type_str][current_name].notes.notes[np.newaxis].T
                )
                data[current_type_str][current_name].notes.index = (
                    data[current_type_str][current_name].notes.index[np.newaxis].T
                )
                data[current_type_str][current_name].notes.ts = (
                    data[current_type_str][current_name].notes.ts[np.newaxis].T
                )

        elif current_type_str == "snips":
            data[current_type_str][current_name].name = current_name
            data[current_type_str][current_name].fs = current_freq

            all_ch = set(data[current_type_str][current_name].chan)

            # make channel filter a list
            if type(channel) is not list:
                channels = [channel]
            else:
                channels = channel
            if 0 in channels:
                channels = list(all_ch)
                use_all_known = True
            channels = sorted(list(set(channels)))
            use_all_known = len(all_ch.intersection(set(channels))) == len(all_ch)

            if not use_all_known:
                # find valid indicies that match our channels
                valid_ind = [
                    i
                    for i, x in enumerate(data[current_type_str][current_name].chan)
                    if x in channels
                ]
                if len(valid_ind) == 0:
                    raise Exception("channels {0} not found".format(repr(channels)))
                if not nodata:
                    all_offsets = data[current_type_str][current_name].data[valid_ind]
                data[current_type_str][current_name].chan = data[current_type_str][
                    current_name
                ].chan[valid_ind]
                data[current_type_str][current_name].sortcode = data[current_type_str][
                    current_name
                ].sortcode[valid_ind]
                data[current_type_str][current_name].ts = data[current_type_str][
                    current_name
                ].ts[valid_ind]
            else:
                if not nodata:
                    all_offsets = data[current_type_str][current_name].data

            if len(data[current_type_str][current_name].chan) > 1:
                data[current_type_str][current_name].chan = (
                    data[current_type_str][current_name].chan[np.newaxis].T
                )
            data[current_type_str][current_name].sortcode = (
                data[current_type_str][current_name].sortcode[np.newaxis].T
            )
            data[current_type_str][current_name].ts = (
                data[current_type_str][current_name].ts[np.newaxis].T
            )

            if not nodata:
                # try to optimally read data from disk in bigger chunks

                max_read_size = 10000000
                iter = 2048
                arr = np.array(range(0, len(all_offsets), iter))
                if len(arr) > 0:
                    markers = all_offsets[arr]
                else:
                    markers = np.array([])

                while (
                    len(markers) > 1
                    and max(np.diff(markers)) > max_read_size
                    and iter > 1
                ):
                    iter = max(iter // 2, 1)
                    markers = all_offsets[range(0, len(all_offsets), iter)]

                arr = range(0, len(all_offsets), iter)

                data[current_type_str][current_name].data = []
                npts = (current_size - np.uint32(10)) * np.uint32(4) // sz
                event_count = 0
                for f in range(len(arr)):
                    tev.seek(markers[f], os.SEEK_SET)

                    # do big-ish read
                    if f == len(arr) - 1:
                        read_size = (all_offsets[-1] - markers[f]) // sz + npts
                    else:
                        read_size = (markers[f + 1] - markers[f]) // sz + npts

                    tev_data = np.frombuffer(
                        tev.read(read_size * sz), current_data_format
                    )

                    # we are covering these offsets
                    start = arr[f]
                    stop = min(arr[f] + iter, len(all_offsets))
                    xxx = all_offsets[start:stop]

                    # convert offsets from bytes to indices in data array
                    relative_offsets = ((xxx - min(xxx)) // sz)[np.newaxis].T
                    ind = relative_offsets + np.tile(
                        range(npts), [len(relative_offsets), 1]
                    )

                    # if we are missing data, there will be duplicates in the ind array
                    _, unique_ind = np.unique(ind[:, 0], return_index=True)
                    if len(unique_ind) != len(ind[:, 0]):
                        # only keep uniques
                        ind = ind[unique_ind, :]
                        # remove last row
                        ind = ind[:-1, :]
                        warnings.warn(
                            "data missing from tev file for store:{0} time:{1}s".format(
                                current_name,
                                np.round(
                                    data[current_type_str][current_name].ts[
                                        event_count + len(ind)
                                    ][0],
                                    3,
                                ),
                            ),
                            Warning,
                        )
                        if len(ind) == 0:
                            continue

                    # add data to big array
                    data[current_type_str][current_name].data.append(
                        tev_data[ind.flatten().astype(np.uint64)].reshape((-1, npts))
                    )
                    event_count += len(ind)

                # convert cell array for output
                if len(data[current_type_str][current_name].data) > 1:
                    data[current_type_str][current_name].data = np.concatenate(
                        data[current_type_str][current_name].data
                    )
                elif np.size(data[current_type_str][current_name].data) == 0:
                    data[current_type_str][current_name].data = []
                else:
                    data[current_type_str][current_name].data = data[current_type_str][
                        current_name
                    ].data[0]

                totalEvents = len(data[current_type_str][current_name].data)
                if len(data[current_type_str][current_name].chan) > 1:
                    data[current_type_str][current_name].chan = data[current_type_str][
                        current_name
                    ].chan[:totalEvents]
                data[current_type_str][current_name].sortcode = data[current_type_str][
                    current_name
                ].sortcode[:totalEvents]
                data[current_type_str][current_name].ts = data[current_type_str][
                    current_name
                ].ts[:totalEvents]

        elif current_type_str == "streams":
            data[current_type_str][current_name].name = current_name
            data[current_type_str][current_name].fs = current_freq

            # catch if the data is in SEV file
            if current_name in sev_names:
                # try to catch if sampling rate is wrong in SEV files
                expected_fs = 0
                if len(block_notes) > 0:
                    for storeNote in block_notes:
                        if (
                            storeNote["StoreName"]
                            == data[current_type_str][current_name].name
                        ):
                            expected_fs = np.float64(storeNote["SampleFreq"])

                d = read_sev(
                    block_path,
                    event_name=current_name,
                    channel=channel,
                    verbose=verbose,
                    ranges=valid_time_range,
                    fs=expected_fs,
                    export=export,
                    scale=scale,
                )
                if d is not None:  # exporter returns None
                    detected_fs = d[current_name].fs
                    if expected_fs > 0 and (np.abs(expected_fs - detected_fs) > 1):
                        warnings.warn(
                            "Detected fs in SEV files was {0} Hz, expected {1} Hz. Using {2} Hz.".format(
                                detected_fs, expected_fs, expected_fs
                            ),
                            Warning,
                        )
                        d[current_name].fs = expected_fs
                    data[current_type_str][current_name] = d[current_name]
                    data[current_type_str][current_name].start_time = time2sample(
                        valid_time_range[0, 0],
                        fs=d[current_name].fs,
                        t1=True,
                        to_time=True,
                    )
            else:
                # make sure SEV files are there if they are supposed to be
                if data[current_type_str][current_name].ucf == 1:
                    warnings.warn(
                        "Expecting SEV files for {0} but none were found, skipping...".format(
                            current_name
                        ),
                        Warning,
                    )
                    continue

                data[current_type_str][current_name].data = [
                    [] for i in range(num_ranges)
                ]
                for jj in range(num_ranges):
                    fc = data[current_type_str][current_name].filtered_chan[jj]
                    if len(fc) < 1:
                        continue

                    # make channel filter into a list
                    if type(channel) is not list:
                        channels = [channel]
                    else:
                        channels = channel
                    if 0 in channels:
                        channels = fc
                    channels = sorted(list(set(channels)))

                    if len(fc) == 1:
                        # there is only one channel here, use them all
                        valid_ind = np.arange(
                            len(data[current_type_str][current_name].filtered_data[jj])
                        )
                        nchan = np.uint64(1)
                    elif len(channels) == 1:
                        valid_ind = fc == channels[0]
                        if not np.any(valid_ind):
                            raise Exception(
                                "channel {0} not found in store {1}".format(
                                    channels[0], current_name
                                )
                            )
                        fc = fc[valid_ind]
                        nchan = np.uint64(1)
                    else:
                        # use selected channels only
                        valid_ind = [i for i, x in enumerate(fc) if x in channels]
                        fc = fc[valid_ind]
                        nchan = np.uint64(len(list(set(fc))))

                    chan_index = np.zeros(nchan, dtype=np.uint64)
                    these_offsets = data[current_type_str][current_name].filtered_data[
                        jj
                    ][valid_ind]

                    # preallocate data array
                    npts = (current_size - np.uint32(10)) * np.uint32(4) // sz
                    # size_in_bytes = current_data_format(1).itemsize * nchan * npts * np.uint64(len(these_offsets)) // nchan
                    data[current_type_str][current_name].data[jj] = np.zeros(
                        [nchan, npts * np.uint64(len(these_offsets)) // nchan],
                        dtype=current_data_format,
                    )

                    max_read_size = 10000000
                    iter = max(min(8192, len(these_offsets) - 1), 1)
                    arr = np.array(range(0, len(these_offsets), iter))
                    if len(arr) > 0:
                        markers = these_offsets[arr]
                    else:
                        markers = np.array([])
                    while (
                        len(markers) > 1
                        and max(np.diff(markers)) > max_read_size
                        and iter > 1
                    ):
                        iter = max(iter // 2, 1)
                        markers = these_offsets[range(0, len(these_offsets), iter)]

                    arr = range(0, len(these_offsets), iter)

                    # create export file handles
                    channel_offset = 0
                    for f in range(len(arr)):
                        tev.seek(markers[f], os.SEEK_SET)

                        # do big-ish read
                        if f == len(arr) - 1:
                            read_size = (these_offsets[-1] - markers[f]) // sz + npts
                        else:
                            read_size = (markers[f + 1] - markers[f]) // sz + npts

                        tev_data = np.frombuffer(
                            tev.read(read_size * sz), current_data_format
                        )

                        # we are covering these offsets
                        start = arr[f]
                        stop = min(arr[f] + iter, len(these_offsets))
                        xxx = these_offsets[start:stop]

                        # convert offsets from bytes to indices in data array
                        relative_offsets = ((xxx - min(xxx)) / sz)[np.newaxis].T
                        ind = relative_offsets + np.tile(
                            range(npts), [len(relative_offsets), 1]
                        )

                        # loop through values, filling array
                        found_empty = False
                        for kk in range(len(relative_offsets)):
                            if nchan > 1:
                                arr_index = channels.index(fc[channel_offset])
                            else:
                                arr_index = 0
                            channel_offset += 1
                            if not np.any(ind[kk, :] <= len(tev_data)):
                                chan_index[arr_index] += npts
                                continue
                            found_empty = False
                            data[current_type_str][current_name].data[jj][
                                arr_index,
                                chan_index[arr_index] : (chan_index[arr_index] + npts),
                            ] = tev_data[ind[kk, :].flatten().astype(np.uint64)]
                            chan_index[arr_index] += npts
                    else:
                        # add data to big cell array
                        # convert cell array for output
                        # be more exact with streams time range filter.
                        # keep timestamps >= valid_time_range(1) and < valid_time_range(2)
                        # index 1 is at header.stores.(current_name).start_time
                        # round timestamps to the nearest sample

                        # actual time the segment starts on
                        td_time = time2sample(
                            data[current_type_str][current_name].start_time[jj],
                            current_freq,
                            to_time=True,
                        )
                        tdSample = time2sample(td_time, current_freq, t1=1)
                        ltSample = time2sample(
                            valid_time_range[0, jj], current_freq, t1=1
                        )
                        minSample = ltSample - tdSample
                        if np.isinf(valid_time_range[1, jj]):
                            maxSample = MAX_UINT64
                        else:
                            etSample = time2sample(
                                valid_time_range[1, jj], current_freq, t1=1
                            )
                            maxSample = etSample - tdSample - 1
                        data[current_type_str][current_name].data[jj] = data[
                            current_type_str
                        ][current_name].data[jj][:, minSample : int(maxSample + 1)]
                        data[current_type_str][current_name].start_time[jj] = (
                            ltSample / current_freq
                        )

                data[current_type_str][current_name].channel = channels
                delattr(data[current_type_str][current_name], "filtered_chan")
                delattr(data[current_type_str][current_name], "filtered_data")
                if len(data[current_type_str][current_name].data) == 1:
                    data[current_type_str][current_name].data = data[current_type_str][
                        current_name
                    ].data[0]
                    if len(data[current_type_str][current_name].data) > 0:
                        if data[current_type_str][current_name].data.shape[0] == 1:
                            data[current_type_str][current_name].data = data[
                                current_type_str
                            ][current_name].data[0]
                    data[current_type_str][current_name].start_time = data[
                        current_type_str
                    ][current_name].start_time[0]

    if not use_outside_headers:
        try:
            tsq.close()
        except:
            pass
    try:
        tev.close()
    except:
        pass

    # find SEV files that weren't in TSQ file
    if "streams" in evtype:
        for sev_name in sev_names:
            # if looking for a particular store and this isn't it, skip it
            if store:
                if isinstance(store, str):
                    if sev_name != store:
                        continue
                elif isinstance(store, list):
                    if sev_name not in store:
                        continue
            if sev_name not in [data.streams[fff].name for fff in data.streams.keys()]:
                d = read_sev(
                    block_path,
                    event_name=sev_name,
                    channel=channel,
                    verbose=verbose,
                    t1=t1,
                    t2=t2,
                    ranges=ranges,
                    export=export,
                    scale=scale,
                )
                if d is not None:  # exporting returns None
                    data.streams[sev_name] = d[sev_name]
                    data.streams[sev_name].start_time = time2sample(
                        t1, t1=True, to_time=True
                    )

    if hasattr(combine, "__len__"):
        for store in combine:
            if not hasattr(data.snips, store):
                raise Exception(
                    "specified combine store name {0} is not in snips structure".format(
                        store
                    )
                )
            data.snips[store] = snip_maker(data.snips[store])

    if bitwise != "":
        if not (hasattr(data.epocs, bitwise) or hasattr(data.scalars, bitwise)):
            raise Exception(
                "specified bitwise store name {0} is not in epocs or scalars".format(
                    bitwise
                )
            )

        nbits = 32
        if hasattr(data.epocs, bitwise):
            bitwisetype = "epocs"
        else:
            bitwisetype = "scalars"

        if not hasattr(data[bitwisetype][bitwise], "data"):
            raise Exception("data field not found")

        # create big array of all states
        sz = len(data[bitwisetype][bitwise].data)
        big_array = np.zeros((nbits + 1, sz))
        if bitwisetype == "epocs":
            big_array[0, :] = data[bitwisetype][bitwise].onset
        else:
            big_array[0, :] = data[bitwisetype][bitwise].ts

        data[bitwisetype][bitwise].bitwise = tdt.StructType()

        # loop through all states
        prev_state = np.zeros(nbits)
        for i in range(sz):
            xxx = np.array([data[bitwisetype][bitwise].data[i]], dtype=np.uint32)

            curr_state = np.unpackbits(xxx.byteswap().view(np.uint8))
            big_array[1 : nbits + 1, i] = curr_state

            # look for changes from previous state
            changes = np.where(np.logical_xor(curr_state, prev_state))[0]

            # add timestamp to onset or offset depending on type of state change
            for ind in changes:
                ffield = "bit" + str(nbits - ind - 1)
                if curr_state[ind]:
                    # nbits-ind reverses it so b0 is bbb(end)
                    if hasattr(data[bitwisetype][bitwise].bitwise, ffield):
                        data[bitwisetype][bitwise].bitwise[
                            ffield
                        ].onset = np.concatenate(
                            [
                                data[bitwisetype][bitwise].bitwise[ffield].onset,
                                [big_array[0, i]],
                            ]
                        )
                    else:
                        data[bitwisetype][bitwise].bitwise[ffield] = tdt.StructType()
                        data[bitwisetype][bitwise].bitwise[ffield].onset = np.array(
                            [big_array[0, i]]
                        )
                        data[bitwisetype][bitwise].bitwise[ffield].offset = np.array([])
                else:
                    data[bitwisetype][bitwise].bitwise[ffield].offset = np.concatenate(
                        [
                            data[bitwisetype][bitwise].bitwise[ffield].offset,
                            [big_array[0, i]],
                        ]
                    )
            prev_state = curr_state

        # add 'inf' to offsets that need them
        for i in range(nbits):
            ffield = "bit" + str(i)
            if hasattr(data[bitwisetype][bitwise].bitwise, ffield):
                if len(data[bitwisetype][bitwise].bitwise[ffield].onset) - 1 == len(
                    data[bitwisetype][bitwise].bitwise[ffield].offset
                ):
                    data[bitwisetype][bitwise].bitwise[ffield].offset = np.concatenate(
                        [data[bitwisetype][bitwise].bitwise[ffield].offset, [np.inf]]
                    )
    signal.complete.emit()
    return data


class TDTLoader(QObject):
    def __init__(self, path: str):
        super(TDTLoader, self).__init__()
        self.path = path
        self.max = None
        self.signals = ProgressSignals()
        self.block = None

    def load_block(self):
        self.block = read_block(self.path, signal=self.signals, evtype=["epocs"])

    def run(self):
        self.load_block()
