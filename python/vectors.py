import math, array

zeroThreshold = 1e-6

class MatrixException(Exception):
	pass


class Angle(object):
	def __init__( self, angle, radian=False ):
		'''set the radian to true on init if the angle is in radians - otherwise degrees are assumed'''
		if radian:
			self.radians = angle
			self.degrees = math.degrees(angle)
		else:
			self.degrees = angle
			self.radians = math.radians(angle)


class Vector(object):
	def __init__( self, x=0, y=0, z=0, w=None ):
		self.x = x
		self.y = y
		self.z = z
		self.w = w
		if isinstance(x,self.__class__):
			x = x.as_tuple()
		if isinstance(x,(list,tuple)):
			self.x = x[0]
			self.y = x[1]
			self.z = x[2]
			if len(x) == 4: self.w = x[3]
	def __iter__( self ):
		return iter(self.as_tuple())
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
			for i in xrange(size):
				element = 0
				col = factor.getCol(i)
				#map(lambda x,y: x*y,self,col)
				for j in xrange(size):
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
	def __eq__( self, other, tolerance=1e-5 ):
		for n,item in enumerate(self):
			if abs( item - other[n] ) > tolerance:
				return False

		return True
	def __ne__( self, other, tolerance=1e-5 ):
		return not self.__eq__(other, tolerance)
	def __mod__( self, other ):
		new = [x%other for x in self]
		return self.__class__(new)
	def __int__( self ):
		return int(self.get_magnitude())
	def __float__( self ):
		return self.get_magnitude()
	def __list__( self ):
		return self.as_list()
	def __tuple__( self ):
		return self.as_tuple()
	def __len__( self ):
		return self.get_size()
	def __getitem__( self, item ):
		#item = min( max( item, 0 ), self.size )
		return (self.x,self.y,self.z,self.w)[item]
	def __setitem__( self, item, value ):
		item = min( max( item, 0 ), self.size )
		setattr( self, ('x','y','z','w')[item], value )
	def __float__( self ):
		return self.mag
	@classmethod
	def Zero( cls, size=4 ):
		return cls( *((0,)*size) )
	@classmethod
	def Random( cls, size=4, range=(0,1) ):
		import random
		list = []
		for n in xrange(size):
			list.append( random.uniform(*range) )

		return cls( *list )
	within = __eq__
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
		if self.w is None: return 3
		return 4
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
		if basisZ is None:
			basisZ = basisX ^ basisY
			basisZ.normalize()

		newX = self.dot(basisX)
		newY = self.dot(basisY)
		newZ = self.dot(basisZ)

		self.x,self.y,self.z = newX,newY,newZ
		self.w = None
	def rotate( self, quat ):
		'''Return the rotated vector v.

        The quaternion must be a unit quaternion.
        This operation is equivalent to turning v into a quat, computing
        self*v*self.conjugate() and turning the result back into a vec3.
        '''
		ww = quat.w * quat.w
		xx = quat.x * quat.x
		yy = quat.y * quat.y
		zz = quat.z * quat.z
		wx = quat.w * quat.x
		wy = quat.w * quat.y
		wz = quat.w * quat.z
		xy = quat.x * quat.y
		xz = quat.x * quat.z
		yz = quat.y * quat.z

		newX = ww * self.x + xx * self.x - yy * self.x - zz * self.x + 2*((xy-wz) * self.y + (xz+wy) * self.z)
		newY = ww * self.y - xx * self.y + yy * self.y - zz * self.y + 2*((xy+wz) * self.x + (yz-wx) * self.z)
		newZ = ww * self.z - xx * self.z - yy * self.z + zz * self.z + 2*((xz-wy) * self.x + (yz+wx) * self.y)

		return self.__class__( newX, newY, newZ )
	def complex( self ):
		return self.__class__( [ complex(v) for v in self.as_tuple() ] )
	def conjugate( self ):
		return self.__class__( [ v.conjugate() for v in self.complex().as_tuple() ] )


class Quaternion(Vector):
	def __init__( self, w=1, x=0, y=0, z=0 ):
		'''initialises a vector from either w,x,y,z args or a Matrix instance'''
		if isinstance(w,Matrix):
			#the matrix is assumed to be a valid rotation matrix
			matrix = w
			d1, d2, d3 = matrix.getDiag()
			t = d1+d2+d3+1.0
			if t > zeroThreshold:
				s = 0.5/math.sqrt(t)
				w = 0.25/s
				x = ( matrix[2][1] - matrix[1][2] )*s
				y = ( matrix[0][2] - matrix[2][0] )*s
				z = ( matrix[1][0] - matrix[0][1] )*s
			else:
				ad1 = d1
				ad2 = d2
				ad3 = d3
				if ad1 >= ad2 and ad1 >= ad3:
					s = math.sqrt(1.0+d1-d2-d3)*2.0
					x = 0.5/s
					y = ( matrix[0][1] + matrix[1][0] )/s
					z = ( matrix[0][2] + matrix[2][0] )/s
					w = ( matrix[1][2] + matrix[2][1] )/s
				elif ad2 >= ad1 and ad2 >= ad3:
					s = math.sqrt(1.0+d2-d1-d3)*2.0
					x = ( matrix[0][1] + matrix[1][0] )/s
					y = 0.5/s
					z = ( matrix[1][2] + matrix[2][1] )/s
					w = ( matrix[0][2] + matrix[2][0] )/s
				else:
					s = math.sqrt(1.0+d3-d1-d2)*2.0
					x = ( matrix[0][2] + matrix[2][0] )/s
					y = ( matrix[1][2] + matrix[2][1] )/s
					z = 0.5/s
					w = ( matrix[0][1] + matrix[1][0] )/s

		Vector.__init__(self,x,y,z,w)
	def __repr__( self ):
		return str(( self.w, self.x, self.y, self.z ))
	def __mul__( self, other ):
		selfClass = self.__class__
		if isinstance( other, selfClass ):
			w1,x1,y1,z1 = self.w,self.x,self.y,self.z
			w2,x2,y2,z2 = other.w,other.x,other.y,other.z
			newW = w1*w2 - x1*x2 - y1*y2 - z1*z2
			newX = w1*x2 + x1*w2 + y1*z2 - z1*y2
			newY = w1*y2 - x1*z2 + y1*w2 + z1*x2
			newZ = w1*z2 + x1*y2 - y1*x2 + z1*w2

			return selfClass(newX,newY,newZ,newW)
		elif isinstance( other, (float,int,long) ):
			return selfClass(self.w*other,self.x*other,self.y*other,self.z*other)
	__rmul__ = __mul__
	def __div__( self, other ):
		assert isinstance(other,(float,int,long))
		return self.__class__(self.w/other,self.x/other,self.y/other,self.z/other)
	@classmethod
	def AxisAngle( cls, axis, angle, normalize=False ):
		'''angle is assumed to be in radians'''
		if normalize: axis.normalize()
		angle /= 2.0
		x, y, z = axis.as_tuple()
		s = math.sin(angle) / math.sqrt(x*x+y*y+z*z)
		newW = math.cos(angle)
		newX = x*s
		newY = y*s
		newZ = z*s
		new = cls(newW,newX,newY,newZ)
		new.normalize()

		return new
	def get_magnitude( self ):
		m = self.w*self.w + self.x*self.x + self.y*self.y + self.z*self.z
		if 1-m > 1e-6:
			math.sqrt(m)
		return m
	__abs__ = get_magnitude
	def as_tuple( self ):
		return (self.w,self.x,self.y,self.z)


class Matrix(object):
	'''deals with square matricies'''
	def __init__( self, values=(), size=4 ):
		'''initialises a matrix from either an iterable container of values or a quaternion.
		in the case of a quaternion the matrix is 3x3'''
		if isinstance( values, self.__class__ ):
			values = values.as_list()
		elif isinstance( values, Quaternion ):
			#NOTE: quaternions result in a 3x3 matrix
			size = 3
			w, x, y, z = values.w, values.x, values.y, values.z
			xx = 2.0*x*x
			yy = 2.0*y*y
			zz = 2.0*z*z
			xy = 2.0*x*y
			zw = 2.0*z*w
			xz = 2.0*x*z
			yw = 2.0*y*w
			yz = 2.0*y*z
			xw = 2.0*x*w
			row0 = 1.0-yy-zz, xy-zw, xz+yw
			row1 = xy+zw, 1.0-xx-zz, yz-xw
			row2 = xz-yw, yz+xw, 1.0-xx-yy

			values = row0+row1+row2
		if len(values) > size*size:
			raise MatrixException('too many args: the size of the matrix is %d and %d values were given'%(size,len(values)))
		self.size = size
		self.rows = []

		for n in xrange(size):
			row = [0]*size
			row[n] = 1
			self.rows.append(row)

		for n in xrange(len(values)):
			self.rows[n/size][n%size] = values[n]
	def __repr__( self ):
		asStr = ''
		for i in xrange(self.size):
			asStr += str( self[i] ) +'\n'

		return asStr
	def __str__( self ):
		return self.__repr__()
	def __add__( self, other ):
		new = self.__class__.Zero(self.size)
		for i in xrange(self.size):
			for j in xrange(self.size):
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
			for i in xrange(self.size):
				for j in xrange(self.size):
					new[i][j] = self[i][j] * other
		elif isinstance( other, Vector ):
			new = Vector()
			for i in xrange(self.size):
				#vector indicies
				for j in xrange(4):
					#matrix indicies
					new[i] += other[j] * self[i][j]
		else:
			new = self.__class__.Zero(self.size)
			for i in xrange(self.size):
				for j in xrange(self.size):
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
		for i in xrange(self.size):
			for j in xrange(self.size):
				if abs( self[i][j] - other[i][j] ) > tolerance:
					return False

		return True
	#some alternative ways to build matrix instances
	@classmethod
	def Zero( cls, size=4 ):
		new = cls([0]*size*size,size)
		return new
	@classmethod
	def Identity( cls, size=4 ):
		rows = [0]*size*size
		for n in xrange(size):
			rows[n+(n*size)] = 1

		return cls(rows,size)
	@classmethod
	def Random( cls, size=4, range=(0,1) ):
		rows = []
		import random
		for n in xrange(size*size):
			rows.append(random.uniform(*range))

		return cls(rows,size)
	@classmethod
	def RotateFromTo( cls, fromVec, toVec, normalize=False ):
		'''Returns a rotation matrix that rotates one vector into another

		The generated rotation matrix will rotate the vector from into
		the vector to. from and to must be unit vectors'''
		e = fromVec*toVec
		f = e.mag

		if f > 1.0-zeroThreshold:
			#from and to vector almost parallel
			fx = abs(fromVec.x)
			fy = abs(fromVec.y)
			fz = abs(fromVec.z)

			if fx < fy:
				if fx < fz: x = Vector(1.0, 0.0, 0.0)
				else: x = Vector(0.0, 0.0, 1.0)
			else:
				if fy < fz: x = Vector(0.0, 1.0, 0.0)
				else: x = Vector(0.0, 0.0, 1.0)

			u = x-fromVec
			v = x-toVec

			c1 = 2.0/(u*u)
			c2 = 2.0/(v*v)
			c3 = c1*c2*u*v

			res = cls(size=3)
			for i in xrange(3):
				for j in xrange(3):
					res[i][j] =  - c1*u[i]*u[j] - c2*v[i]*v[j] + c3*v[i]*u[j]
				res[i][i] += 1.0

			return res
		else:
			#the most common case unless from == to, or from == -to
			v = fromVec^toVec
			h = 1.0/(1.0 + e)
			hvx = h*v.x
			hvz = h*v.z
			hvxy = hvx*v.y
			hvxz = hvx*v.z
			hvyz = hvz*v.y

			row0 = e + hvx*v.x, hvxy - v.z, hvxz + v.y
			row1 = hvxy + v.z, e + h*v.y*v.y,hvyz - v.x
			row2 = hvxz - v.y, hvyz + v.x, e + hvz*v.z

			return cls( row0+row1+row2 )
	@classmethod
	def FromEulerXYZ( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		AE = A*E
		AF = A*F
		BE = B*E
		BF = B*F

		row0 = ( C*E, -C*F, D )
		row1 = ( AF+BE*D, AE-BF*D, -B*C )
		row2 = ( BF-AE*D, BE+AF*D, A*C )

		return cls( row0+row1+row2, 3 )
	@classmethod
	def FromEulerYZX( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		AC = A*C
		AD = A*D
		BC = B*C
		BD = B*D

		row0 = ( C*E, BD-AC*F, BC*F+AD )
		row1 = ( F, A*E, -B*E )
		row2 = ( -D*E, AD*F+BC, AC-BD*F )

		return cls( row0+row1+row2, 3 )
	@classmethod
	def FromEulerZXY( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		CE = C*E
		CF = C*F
		DE = D*E
		DF = D*F

		row0 = ( CE-DF*B, -A*F, DE+CF*B )
		row1 = ( CF+DE*B, A*E, DF-CE*B )
		row2 = ( -A*D, B, A*C )

		return cls( row0+row1+row2, 3 )
	@classmethod
	def FromEulerXZY( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		AC = A*C
		AD = A*D
		BC = B*C
		BD = B*D

		row0 = ( C*E, -F, D*E )
		row1 = ( AC*F+BD, A*E, AD*F-BC )
		row2 = ( BC*F-AD, B*E, BD*F+AC )

		return cls( row0+row1+row2, 3 )
	@classmethod
	def FromEulerYXZ( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		CE = C*E
		CF = C*F
		DE = D*E
		DF = D*F

		row0 = ( CE+DF*B, DE*B-CF, A*D )
		row1 = ( A*F, A*E, -B )
		row2 = ( CF*B-DE, DF+CE*B, A*C )

		return cls( row0+row1+row2, 3 )
	@classmethod
	def FromEulerZYX( cls, x, y, z ):
		A = math.cos(x)
		B = math.sin(x)
		C = math.cos(y)
		D = math.sin(y)
		E = math.cos(z)
		F = math.sin(z)
		AE = A*E
		AF = A*F
		BE = B*E
		BF = B*F

		row0 = ( C*E, BE*D-AF, AE*D+BF )
		row1 = ( C*F, BF*D+AE, AF*D-BE )
		row2 = ( -D, B*C, A*C )

		return cls( row0+row1+row2, 3 )
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
		for n in xrange(self.size):
			column[n] = self.rows[n][col]

		return column
	def setCol( self, col, newCol ):
		newColActual = []
		for n in xrange(min(self.size,len(newCol))):
			self.rows[n] = newCol[n]
			newColActual.append(newCol[n])

		return newColActual
	def getDiag( self ):
		diag = []
		for i in xrange(self.size):
			diag.append( self[i][i] )
		return diag
	def setDiag( self, diag ):
		for i in xrange(self.size):
			self[i][i] = diag[i]
		return diag
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
		for i in xrange(self.size):
			for j in xrange(self.size):
				new[i][j] = self[j][i]

		return new
	def transpose3by3( self ):
		new = self.copy()
		for i in xrange(3):
			for j in xrange(3):
				new[i][j] = self[j][i]

		return new
	def copy( self ):
		rows = []
		for n in xrange(self.size):
			rows += self[n]

		return self.__class__( rows, self.size )
	def det( self ):
		'''calculates the determinant for an arbitrarily sized square matrix'''
		d = 0
		if self.size <= 0: return 1
		for i in xrange(self.size):
			sign = (1,-1)[ i % 2 ]
			cofactor = self.cofactor(i,0)
			d += sign * self[i][0] * cofactor.det()

		return d
	determinant = det
	def cofactor( self, aI, aJ ):
		cf = self.__class__(size=self.size-1)
		cfi = 0
		for i in xrange(self.size):
			if i == aI: continue
			cfj = 0
			for j in xrange(self.size):
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
		return ( abs(self.det()) - 1 < 1e-6 )
	def inverse( self ):
		'''Each element of the inverse is the determinant of its minor
		divided by the determinant of the whole'''
		isSingular,det = self.isSingular()
		if isSingular: return self.copy()

		new = self.__class__.Zero(self.size)
		for i in xrange(self.size):
			for j in xrange(self.size):
				sign = (1,-1)[ (i+j) % 2 ]
				new[i][j] = sign * self.cofactor(i,j).det()

		new /= det

		return new.transpose()
	def adjoint( self ):
		new = self.__class__.Zero(self.size)
		for i in xrange(self.size):
			for j in xrange(self.size):
				new[i][j] = (1,-1)[(i+j)%2] * self.cofactor(i,j).det()

		return new.transpose()
	def ortho( self ):
		'''return a matrix with orthogonal base vectors'''
		x = Vector(self[0][:3])
		y = Vector(self[1][:3])
		z = Vector(self[2][:3])

		xl = x.mag
		xl *= xl
		y = y - ((x*y)/xl)*x
		z = z - ((x*z)/xl)*x

		yl = y.mag
		yl *= yl
		z = z - ((y*z)/yl)*y

		row0 = ( x.x, y.x, z.x )
		row1 = ( x.y, y.y, z.y )
		row2 = ( x.z, y.z, z.z )

		return self.__class__(row0+row1+row2,size=3)
	def decompose( self ):
		'''decomposes the matrix into a rotation and scaling part.
	    returns a tuple (rotation, scaling). the scaling part is given
	    as a 3-tuple and the rotation a Matrix(size=3)'''
		dummy = self.ortho()

		x = dummy[0]
		y = dummy[1]
		z = dummy[2]
		xl = x.mag
		yl = y.mag
		zl = z.mag
		scale = xl,yl,zl

		x/=xl
		y/=yl
		z/=zl
		dummy.setCol(0,x)
		dummy.setCol(1,y)
		dummy.setCol(2,z)
		if dummy.det() < 0:
			dummy.setCol(0,-x)
			scale.x = -scale.x

		return (dummy, scale)
	def get_position( self ):
		return Vector( *self[3][:3] )
	#the following methods return euler angles of a rotation matrix
	def get_rotXYZ( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		D = r1[2]
		y = math.asin(D)
		C = math.cos(y)

		if C > zeroThreshold:
			x = math.acos(r3[2]/C)
			z = math.acos(r1[0]/C)
		else:
			z = 0.0
			x = math.acos(r2[1])

		return (x,y,z)
	def get_rotYZX( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		F = r2[0]
		z = math.asin(F)
		E = math.cos(z)

		if E > zeroThreshold:
			x = math.acos(r2[1]/E)
			y = math.acos(r1[0]/E)
		else:
			y = 0.0
			x = math.asin(r3[1])

		return (x,y,z)
	def get_rotZXY( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		B = r3[1]
		x = math.asin(B)
		A = math.cos(x)

		if A > zeroThreshold:
			y = math.acos(r3[2]/A)
			z = math.acos(r2[1]/A)
		else:
			z = 0.0
			y = math.acos(r1[0])

		return (x,y,z)
	def get_rotXZY( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		F = -r1[1]
		z = math.asin(F)
		E = math.cos(z)

		if E > zeroThreshold:
			x = math.acos(r2[1]/E)
			y = math.acos(r1[0]/E)
		else:
			y = 0.0
			x = math.acos(r3[2])

		return (x,y,z)
	def get_rotYXZ( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		B = -r2[2]
		x = math.asin(B)
		A = math.cos(x)

		if A > zeroThreshold:
			y = math.acos(r3[2]/A)
			z = math.acos(r2[1]/A)
		else:
			z = 0.0
			y = math.acos(r1[0])

		return (x,y,z)

	def get_rotZYX( self ):
		r1 = self[0]
		r2 = self[1]
		r3 = self[2]

		D = -r3[0]
		y = math.asin(D)
		C = math.cos(y)

		if C > zeroThreshold:
			x = math.acos(r3[2]/C)
			z = math.acos(r1[0]/C)
		else:
			z = 0.0
			x = math.acos(-r2[1])

		return (x,y,z)
	#some conversion routines
	def as_list( self ):
		list = []
		for i in xrange(self.size):
			list.extend(self[i])

		return list
	def as_tuple( self ):
		return tuple( self.as_list() )


#end