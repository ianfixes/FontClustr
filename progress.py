
import math

# A collection of callbacks for printing things to the screen
class Progress(object):

    def __init__(self):
        self.reset();

    def reset(self):
        self.task_name = None
        self.steps = None
        self.steps_completed = None

    def working(self):
        return self.steps is not None

    def begin_task(self, task_name, steps, message):
        self.task_name = task_name
        self.steps = steps
        self.steps_completed = 0
        self.on_begin(message)

    def end_task(self, message):
        self.on_end(message)
        self.reset()

    def advance(self, steps, error = None):
        self.steps_completed += steps
        self.on_advance(self.task_name, float(self.steps_completed) / self.steps, error)

    def on_begin(self, message):
        print message

    def on_advance(self, task_name, ratio, error = None):
        if error:
            print (" " * len(task_name)), " -- oops! ", error
        else:
            percentdone = "[%02.0f%%]" % math.floor(ratio * 100)
            print task_name, percentdone

    def on_end(self, message):
        print message


# only print out progress at discrete intervals
class DiscreteProgress(Progress):

    def __init__(self, increment):
        self.increment = increment
        self.last_increment = None
        super(DiscreteProgress, self).__init__()

    def on_begin(self, message):
        self.last_increment = 0
        super(DiscreteProgress, self).on_begin(message)

    def on_advance(self, task_name, ratio, error = None):
        if error is not None:
            super(DiscreteProgress, self).on_advance(task_name, ratio, error)
        elif ratio >= self.last_increment + self.increment:
            super(DiscreteProgress, self).on_advance(task_name, ratio, error)
            self.last_increment += self.increment
