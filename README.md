# Video Scoring Application
https://github.com/DannyAlas/qt-vid-score/assets/81212794/bc15fd36-d8d4-492d-874f-b66c2580817c

Aims to assist in behavioral scoring with automatic behavior detection and model training features.

## Keybinds
Can be edited in the settings menu. The default keybinds are as follows:
| Action Name                                     | Keybind        | Explanation                                             |
|-------------------------------------------------|----------------|---------------------------------------------------------|
| Exit                                            | Q              | Quit the program and save all timestamps to file.       |
| Help                                            | H              | Display the help menu with available commands.          |
| Save Timestamp                                  | S              | Save the timestamp of the current frame.                |
| Show Stats                                      | T              | Display current statistics and program status.          |
| Undo                                            | Ctrl+Z         | Undo the last action performed.                         |
| Redo                                            | Ctrl+Shift+Z   | Redo the last action that was undone.                   |
| Toggle Play                                     | Space          | Pause or play the current playback.                     |
| Seek Forward Small Frames                       | D              | Move forward by a small number of frames.               |
| Seek Back Small Frames                          | A              | Move backward by a small number of frames.              |
| Seek Forward Medium Frames                      | Shift+D        | Move forward by a medium number of frames.              |
| Seek Back Medium Frames                         | Shift+A        | Move backward by a medium number of frames.             |
| Seek Forward Large Frames                       | P              | Move forward by a large number of frames.               |
| Seek Back Large Frames                          | O              | Move backward by a large number of frames.              |
| Seek to First Frame                             | 1              | Jump to the first frame in the sequence.                |
| Seek to Last Frame                              | 0              | Jump to the last frame in the sequence.                 |
| Increase Playback Speed                         | X              | Increase the playback speed by a predefined amount.     |
| Decrease Playback Speed                         | Z              | Decrease the playback speed by a predefined amount.     |
| Increment Selected Timestamp by Seek Small      | Down           | Increment the selected timestamp by a small amount.     |
| Decrement Selected Timestamp by Seek Small      | Up             | Decrement the selected timestamp by a small amount.     |
| Increment Selected Timestamp by Seek Medium     | Shift+Down     | Increment the selected timestamp by a medium amount.    |
| Decrement Selected Timestamp by Seek Medium     | Shift+Up       | Decrement the selected timestamp by a medium amount.    |
| Increment Selected Timestamp by Seek Large      | Ctrl+Down      | Increment the selected timestamp by a large amount.     |
| Decrement Selected Timestamp by Seek Large      | Ctrl+Up        | Decrement the selected timestamp by a large amount.     |
| Move to Last Onset/Offset                       | Left           | Move to the last onset/offset timestamp.                |
| Move to Next Onset/Offset                       | Right          | Move to the next onset/offset timestamp.                |
| Move to Last Timestamp                          | Shift+Left     | Move to the last timestamp in the sequence.             |
| Move to Next Timestamp                          | Shift+Right    | Move to the next timestamp in the sequence.             |
| Select Current Timestamp                        | Enter          | Select and highlight the current timestamp.             |
| Delete Selected Timestamp                       | Delete         | Permanently delete the selected timestamp.              |
