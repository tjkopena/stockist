
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")


from stockist import square
import logberry

logberry.start()

api = square.client(square.load_configuration())
api.delete_catalog()

logberry.stop()
