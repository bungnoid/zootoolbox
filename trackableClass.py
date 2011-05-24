
from typeFactories import trackableTypeFactory


def trackableClassFactory( superClass=object ):
	'''
	returns a class that tracks subclasses.  for example, if you had classB(classA)
	ad you wanted to track subclasses, you could do this:

	class classB(trackableClassFactory( classA )):
		...

	a classmethod called GetSubclasses is created in the returned class for
	querying the list of subclasses
	'''
	class TrackableClass(superClass): __metaclass__ = trackableTypeFactory()
	return TrackableClass


#end
