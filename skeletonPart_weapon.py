
from baseSkeletonBuilder import *


class WeaponRoot(SkeletonPart):

	@classmethod
	def _build( cls, parent=None, weaponName='', **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		j = createJoint( '%s_%d' % (weaponName, idx+1) )
		cmd.parent( j, parent, r=True )

		#move it out a bit
		for ax in AXES: setAttr( '%s.t%s' % (j, ax), partScale )

		return [ j ]
	def _align( self, _initialAlign=False ):
		'''
		leave weapon parts alone - the user should define how they're aligned always
		'''
		pass


#end
