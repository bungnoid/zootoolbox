
from sobject import SObject, ListStream
from unittest import TestCase

class SObjectTests(TestCase):
	def runTest( self ):
		self.testGetAttr()
		self.testSerializationRoundTrip()
		self.testConversionFromDict()
	def testGetAttr( self ):
		attrNames = 'apple', 'banana', 'pears', 'orange', 'peach', 'nectarine', 'grape', 'watermelon'
		attrValues = range( len( attrNames ) )
		obj = SObject( *zip( attrNames, attrValues ) )
		assert obj.getAttrs() == attrNames
		for attr, value in zip( attrNames, attrValues ):
			assert value == getattr( obj, attr )

		#test simple case equality
		assert obj == SObject( *zip( attrNames, attrValues ) )
	def testSerializationRoundTrip( self ):
		root = SObject()
		root.aString = "other thing"
		root.anotherStr = "bananas"
		root.anInt = 12

		s2 = SObject( ('some_float', 200.0), ('crazy_list', [1,2,3]), ('someBool', True), ('unicode_test', u'some unicode value "with crap in it"\nand a newline!') )
		root.aSubObject = s2

		s3 = SObject( ('duplicate_ref_to_s2', s2), ('a_stupidly_long_attribute_name_to_test_whether_it_works_ok_with_serialization', 0x902) )

		s4 = SObject( ('recursive_ref_to_root', root), ('anotherTokenAttribute', -100) )
		root.s4 = s4

		assert s4.recursive_ref_to_root is root

		#serialize the object and
		listStream = ListStream()
		root.serialize( listStream )
		unserializedRoot = SObject.Unserialize( listStream )
		assert root == unserializedRoot

		#test that the object references unserialized properly
		assert unserializedRoot is unserializedRoot.s4.recursive_ref_to_root
	def testConversionFromDict( self ):
		nestedDicts = { 'something': 12,
		                'otherthing': 'blah blah blah',
		                'nestedDict': { 'bleargh': 111 }
		                }

		subDict = { 'cyclic_ref': nestedDicts }
		nestedDicts[ 'cyclic_ref' ] = subDict

		convertedFromDict = SObject.FromDict( nestedDicts )

SObjectTests().run()

#end
