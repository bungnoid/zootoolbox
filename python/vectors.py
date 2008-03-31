'''
super simple vector class and vector functionality.  i wrote this simply because i couldn't find
anything that was easily accessible and quick to write.  this may just go away if something more
comprehensive/mature is found
'''

import math


class MatrixException(Exception):
	pass


class Vector(object):
	#__slots__ = ('x','y','z','w')
	def __init__( self, x=0, y=0, z=0, w=None ):
		self.x = x
		self.y = y
		self.z = z
		self.w = w
		if isinstance(x,(list,tuple)):
			self.x = x[0]
			self.y = x[1]
			self.z = x[2]
			if len(x) == 4: self.w = x[3]
	def __repr__( self ):
		if self._is4Vec: return str(( self.x, self.y, self.z, self.w ))
		return str(( self.x, self.y, self.z ))
	def __str__( self ):
		return str(repr(self))
	def __add__( self, other ):
		if self._is4Vec: return self.__class__( self.x+other.x, self.y+other.y, self.z+other.z, self.w+other.w )
		else: return self.__class__( self.x+other.x, self.y+other.y, self.z+other.z )
	def __sub__( self, other ):
		return self + -other
	def __mul__( self, factor ):
		if isinstance(factor,Vector):
			return self.dot(factor)
		elif isinstance(factor,Matrix):
			new = self.__class__()
			size = self.size
			for i in range(size):
				element = 0
				col = factor.getCol(i)
				for j in range(size):
					element += self[j]*col[j]
				new[i] = element

			return new
		else:
			if self._is4Vec: return self.__class__( self.x*factor, self.y*factor, self.z*factor, self.w*factor )
			else: return self.__class__( self.x*factor, self.y*factor, self.z*factor )
	def __div__( self, denominator ):
		if self._is4Vec: return self.__class__( self.x/denominator, self.y/denominator, self.z/denominator, self.w/denominator )
		return self.__class__( self.x/denominator, self.y/denominator, self.z/denominator )
	def __invert__( self ):
		return -self
	def __neg__( self ):
		return self*-1
	def __getitem__( self, item ):
		item = min( max( item, 0 ), self.size )
		return (self.x,self.y,self.z,self.w)[item]
	def __setitem__( self, item, value ):
		item = min( max( item, 0 ), self.size )
		setattr( self, ('x','y','z','w')[item], value )
	@classmethod
	def Zero( cls, size=4 ):
		return cls( *((0,)*size) )
	@classmethod
	def Random( cls, size=4 ):
		import random
		list = []
		for n in range(size):
			list.append( random.random() )

		return cls( *list )
	def copy( self ):
		return self.__class__( *self.as_tuple() )
	def dot( self, other ):
		dot = self.x*other.x + self.y*other.y + self.z*other.z
		if self._is4Vec: dot += self.w*other.w

		return dot
	def __rxor__( self, other ):
		#used for cross product - called using a**b
		#NOTE: the cross product isn't defined for a 4 vector - so it always ignores the w
		x = self.y*other.z - self.z*other.y
		y = self.z*other.x - self.x*other.z
		z = self.x*other.y - self.y*other.x
		return self.__class__(x,y,z)
	cross = __rxor__
	def __is4Vec( self ):
		if self.w != None: return True
		return False
	_is4Vec = property(__is4Vec)
	def get_size( self ):
		if self.w != None: return 4
		return 3
	size = property(get_size)
	def get_magnitude( self ):
		if self._is4Vec: return math.sqrt(self.x**2 + self.y**2 + self.z**2 + self.w**2)
		return math.sqrt(self.x**2 + self.y**2 + self.z**2)
	def set_magnitude( self, factor ):
		factor /= self.length
		self.x *= factor
		self.y *= factor
		self.z *= factor
		if self._is4Vec: self.w *= factor
	magnitude = property(get_magnitude,set_magnitude)
	mag = property(get_magnitude,set_magnitude)
	length = property(get_magnitude,set_magnitude)
	def normalize( self ):
		'''normalizes the vector in place'''
		len = self.length
		self.x /= len
		self.y /= len
		self.z /= len
		if self._is4Vec: self.w /= len
	def as_tuple( self ):
		if self._is4Vec: return (self.x,self.y,self.z,self.w)
		return (self.x,self.y,self.z)
	def as_list( self ):
		return list( self.as_tuple() )
	def change_space( self, basisX, basisY, basisZ=None ):
		'''will re-parameterize this vector to a different space
		NOTE: the basisZ is optional - if not given, then it will be computed from X and Y
		NOTE: changing space isn't supported for 4-vectors'''
		if basisZ == None:
			basisZ = basisX ^ basisY
			basisZ.normalize()

		newX = self.dot(basisX)
		newY = self.dot(basisY)
		newZ = self.dot(basisZ)

		self.x,self.y,self.z = newX,newY,newZ
		self.w = None
	def complex(self):
		return self.__class__( [ complex(v) for v in self.as_tuple() ] )
	def conjugate(self):
		return self.__class__( [ v.conjugate() for v in self.complex().as_tuple() ] )


class Matrix(object):
	'''deals with square matricies'''
	#__slots__ = ('size','rows')  #slots are commented out because they seem to be slightly slower than the standard __dict__ attributes
	def __init__( self, values=(), size=4 ):
		if len(values) > size*size:
			raise MatrixException('too many args: the size of the matrix is %d and %d values were given'%(size,len(values)))
		self.size = size
		self.rows = []

		for n in range(size):
			row = [0]*size
			row[n] = 1
			self.rows.append(row)

		for n in range(len(values)):
			self.rows[n/size][n%size] = values[n]
	def __repr__( self ):
		asStr = ''
		for i in range(self.size): 
			asStr += str( self[i] ) +'\n'

		return asStr
	def __str__( self ):
		return self.__repr__()
	def __add__( self, other ):
		new = self.__class__.Zero(self.size)
		for i in range(self.size):
			for j in range(self.size):
				new[i][j] = self[i][j] + other[i][j]

		return new
	def __sub__( self, other ):
		new = self.__class__.Zero(self.size)
		new = self + (other*-1)

		return new
	def __mul__( self, other ):
		new = None
		if isinstance( other, (float,int) ):
			new = self.__class__.Zero(self.size)
			for i in range(self.size):
				for j in range(self.size):
					new[i][j] = self[i][j] * other
		elif isinstance( other, Vector ):
			new = Vector()
			for i in range(self.size):
				#vector indicies
				for j in range(4):
					#matrix indicies
					new[i] += other[j] * self[i][j]
		else:
			new = self.__class__.Zero(self.size)
			for i in range(self.size):
				for j in range(self.size):
					new[i][j] = Vector( *self.getRow(i) ) * Vector( *other.getCol(j) )

		return new
	def __div__( self, other ):
		return self.__mul__(1.0/other)
	def __getitem__( self, item ):
		'''matrix is indexed as: self[row][column]'''
		return self.rows[item]
	def __setitem__( self, item, newRow ):
		if len(newRow) != self.size: raise MatrixException( 'row length not of correct size' )
		self.rows[item] = newRow
	def __eq__( self, other ):
		return self.isEqual(other)
	def __ne__( self, other ):
		return not self.isEqual(other)
	def isEqual( self, other, tolerance=1e-5 ):
		if self.size != other.size:
			return False
		for i in range(self.size):
			for j in range(self.size):
				if abs( self[i][j] - other[i][j] ) > tolerance:
					return False

		return True
	@classmethod
	def Zero( cls, size=4 ):
		new = cls([0]*size*size,size)
		return new
	@classmethod
	def Identity( cls, size=4 ):
		rows = [0]*size*size
		for n in range(size):
			rows[n+(n*size)] = 1

		return cls(rows,size)
	@classmethod
	def Random( cls, size=4 ):
		rows = []
		import random
		for n in range(size*size):
			#rows.append(random.random())
			rows.append(random.randint(0,10))

		return cls(rows,size)
	def getRow( self, row ):
		return self.rows[row]
	def setRow( self, row, newRow ):
		if len(newRow) > self.size: newRow = newRow[:self.size]
		if len(newRow) < self.size:
			newRow.extend( [0] * (self.size-len(newRow)) )

		self.rows = newRow

		return newRow
	def getCol( self, col ):
		column = [0]*self.size
		for n in range(self.size):
			column[n] = self.rows[n][col]

		return column
	def setCol( self, col, newCol ):
		newColActual = []
		for n in range(min(self.size,len(newCol))):
			self.rows[n] = newCol[n]
			newColActual.append(newCol[n])

		return newColActual
	def swapRow( self, nRowA, nRowB ):
		rowA = self.getRow(nRowA)
		rowB = self.getRow(nRowB)
		tmp = rowA
		self.setRow(nRowA,rowB)
		self.setRow(nRowB,tmp)
	def swapCol( self, nColA, nColB ):
		colA = self.getCol(nColA)
		colB = self.getCol(nColB)
		tmp = colA
		self.setCol(nColA,colB)
		self.setCol(nColB,tmp)
	def transpose( self ):
		new = self.__class__.Zero(self.size)
		for i in range(self.size):
			for j in range(self.size):
				new[i][j] = self[j][i]

		return new
	def transpose3by3( self ):
		new = self.copy()
		for i in range(3):
			for j in range(3):
				new[i][j] = self[j][i]

		return new
	def copy( self ):
		rows = []
		for n in range(self.size):
			rows += self[n]

		return self.__class__( rows, self.size )
	def det( self ):
		'''calculates the determinant for an arbitrarily sized square matrix'''
		d = 0
		if self.size <= 0: return 1
		for i in range(self.size):
			sign = (1,-1)[ i % 2 ]
			cofactor = self.cofactor(i,0)
			d += sign * self[i][0] * cofactor.det()

		return d
	determinant = det
	def cofactor( self, aI, aJ ):
		cf = self.__class__(size=self.size-1)
		cfi = 0
		for i in range(self.size):
			if i == aI: continue
			cfj = 0
			for j in range(self.size):
				if j == aJ: continue
				cf[cfi][cfj] = self[i][j]
				cfj += 1
			cfi += 1

		return cf
	minor = cofactor
	def isSingular( self ):
		det = self.det()
		if abs(det) < 1e-6: return True,0
		return False,det
	def isRotation( self ):
		'''rotation matricies have a determinant of 1'''
		if abs(self.det()) - 1 < 1e-6: return True
		return False
	def inverse( self ):
		'''Each element of the inverse is the determinant of its minor
		divided by the determinant of the whole'''
		isSingular,det = self.isSingular()
		if isSingular: return self.copy()

		new = self.__class__.Zero(self.size)
		for i in range(self.size):
			for j in range(self.size):
				sign = (1,-1)[ (i+j) % 2 ]
				new[i][j] = sign * self.cofactor(i,j).det()

		new /= det

		return new.transpose()
	def as_list( self ):
		list = []
		for i in range(self.size):
			list.extend(self[i])

		return list
	def as_tuple( self ):
		return tuple( self.as_list() )


def test():
	#create some random matricies and make sure things are working
	import time
	time.clock()

	def inverseTest( size, numIts=10 ):
		identity = Matrix.Identity(size)
		for n in range(numIts):
			testMatA = Matrix.Random(size)
			testMatAInv = testMatA.inverse()
			mult = testMatA*testMatAInv 

			if not mult.isEqual(identity,0.001):
				assert isinstance(mult,Matrix)
				if not mult.isSingular():
					print 'failed to calculate inverse for matrix of size',size
					print mult

	inverseTest(2)
	inverseTest(3)
	inverseTest(4,250)

	#for n in range(20000):
		#a=Matrix.Random()
		#b=a.as_tuple()
		#len(b)

	secs = time.clock()
	print 'seconds taken',secs

#test()


#end