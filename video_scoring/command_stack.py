
from typing import List
from abc import ABC, abstractmethod

class Command(ABC):
    """ TODO
    Implements a command for undo/redo functionality.

    Override the execute, undo, and redo methods to implement the desired functionality.
    
    """
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass

class CommandStack:
    """
    Implements a command stack for undo/redo functionality

    Smiply, if a method should be undoable it will be responsible for adding a Command object to the stack.
    The Command object will implement the appropriate methods and data for undoing and redoing the action.

    The CommandStack will be the interface utilized by the MainWindow to undo/redo actions.
    It will be responsible for executing the commands and updating the stack.

    If needed, future implementations may want to consider managing the stack size, the posiblity to
    excute long running commands a separate thread
    
    """
    def __init__(self):
        self.stack: List[Command] = []
        self.index = -1

    def undo(self):
        if self.index >= 0:
            self.index -= 1
            self.stack[self.index].undo()

    def redo(self):
        if self.index < len(self.stack) - 1:
            self.index += 1
            self.stack[self.index].redo()

    def add_command(self, command: Command):
        # clear everything after the current index since we're branching
        self.stack = self.stack[:self.index + 1]
        self.stack.append(command)
        self.index += 1
        print(len(self.stack))
        if len(self.stack) > 1000:
            self.stack = self.stack[1:]
            self.index -= 1
   