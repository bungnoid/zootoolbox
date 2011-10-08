
import os
import sys

from sobject import SObject
from unittest import TestCase


class SObjectTests(TestCase):
	_TEST_FILE = '~/_sobject_devtest.txt'

	def runTest( self ):
		self.testGetAttr()

		sobject = self.constructData()
		self.testRoundTrip( sobject )
		self.testSerialization( sobject )

		self.testConversionFromDict()
	def getTestFilepath( self ):
		return os.path.expanduser( self._TEST_FILE )
	def tearDown( self ):
		testFilepath = self.getTestFilepath()
		os.remove( testFilepath )
	def constructData( self ):
		root = SObject()
		root.aString = "other thing"
		root.anotherStr = "bananas"
		root.anInt = 12

		root.s2 = SObject( ('some_float', 200.0), ('someBool', True), ('unicode_test', u'some unicode value "with crap in it"\nand a newline!') )
		root.s2.crazy_list = [1,2.5,'3',True]

		root.s3 = SObject( ('duplicate_ref_to_s2', root.s2), ('a_stupidly_long_attribute_name_to_test_whether_it_works_ok_with_serialization', 0x902) )

		root.s4 = SObject( ('recursive_ref_to_root', root), ('anotherTokenAttribute', -100) )

		#test SObjects in lists - mixed with other stuff
		root.s5 = SObject()
		root.s5.objList = [root.s2, root.s3, root.s5, 1, 3.5, True]
		root.s5.largeList = range(1000)

		#test tuples
		root.s6 = SObject( ('aTuple', (1,2,3)), ('objTuple', (SObject(), SObject())) )

		assert root.s4.recursive_ref_to_root is root

		return root
	def testGetAttr( self ):
		attrNames = 'apple', 'banana', 'pears', 'orange', 'peach', 'nectarine', 'grape', 'watermelon'
		attrValues = range( len( attrNames ) )
		obj = SObject( *zip( attrNames, attrValues ) )
		assert obj.getAttrs() == attrNames
		for attr, value in zip( attrNames, attrValues ):
			assert value == getattr( obj, attr )

		#test simple case equality
		assert obj == SObject( *zip( attrNames, attrValues ) )
	def testSerialization( self, sobject ):
		filepath = self.getTestFilepath()

		#test writing to file stream
		with open( filepath, 'w' ) as fStream:
			sobject.serialize( fStream )

		#test reading from file stream
		with open( filepath ) as fStream:
			return SObject.Unserialize( fStream )

		filepath.delete()
		assert not filepath.exists()

		#test writing and reading from disk
		sobject.write( filepath )
		assert filepath.exists()

		unserialized = SObject.Load( filepath )
		assert unserialized == sobject

		filepath.delete()
		assert not filepath.exists()
	def testRoundTrip( self, sobject ):

		#this forces serialization of the root sobject
		asStr = str( sobject )

		#round trip the sobject
		roundTripped = sobject._roundTrip()

		#ensure the structures are identical - this should in theory act as a fairly comprehensive test
		#of serialization and unserialization provided the test data is also comprehensive
		assert sobject == roundTripped

		#test that the object references unserialized properly
		assert roundTripped is roundTripped.s4.recursive_ref_to_root

		assert len( roundTripped.s2.crazy_list ) == len( sobject.s2.crazy_list )
		assert len( roundTripped.s5.objList ) == len( sobject.s5.objList )
		assert type( roundTripped.s6.aTuple ) is tuple
		assert type( roundTripped.s6.objTuple[0] ) is SObject
	def testConversionFromDict( self ):
		nestedDicts = dict( something=12,
		                otherthing='blah blah blah',
		                someList=[1,2,3],
		                listOfDicts=[ dict(), dict(anInt=1, aStr='yes, me is a str') ],
		                nestedDict=dict( bleargh=111 )
		                )

		nestedDicts[ 'cyclic_ref' ] = nestedDicts

		convertedFromDict = SObject.FromDict( nestedDicts )
		convertedDict = convertedFromDict.toDict()
		assert convertedDict['cyclic_ref'] is convertedDict

		#assert convertedDict == nestedDicts  #python doesn't like comparing cyclically nested dicts...
		nestedDicts.pop( 'cyclic_ref' )

		asStr = str( convertedFromDict )
		convertedDict = SObject.FromDict( nestedDicts ).toDict()
		assert convertedDict == nestedDicts

SObjectTests().run()

#end
