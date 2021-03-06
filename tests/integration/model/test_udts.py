# Modifications Copyright 2016-2017 Reddit, Inc.
#
# Copyright 2013-2016 DataStax, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
try:
    import unittest2 as unittest
except ImportError:
    import unittest  # noqa

from datetime import datetime, date, time
from decimal import Decimal
from unittest import mock
from uuid import UUID, uuid4

from cqlmapper.models import Model
from cqlmapper.usertype import UserType, UserTypeDefinitionException
from cqlmapper import columns, connection
from cqlmapper.management import (
    sync_table,
    sync_type,
    create_keyspace_simple,
    drop_keyspace,
    drop_table,
)
from cassandra.util import Date, Time

from tests.integration import PROTOCOL_VERSION
from tests.integration.base import BaseCassEngTestCase


class UserDefinedTypeTests(BaseCassEngTestCase):
    def setUp(self):
        super(UserDefinedTypeTests, self).setUp()
        if PROTOCOL_VERSION < 3:
            raise unittest.SkipTest(
                "UDTs require native protocol 3+, currently using: {0}".format(PROTOCOL_VERSION)
            )

    def test_can_create_udts(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        sync_type(self.conn, User)
        user = User(age=42, name="John")
        self.assertEqual(42, user.age)
        self.assertEqual("John", user.name)

        # Add a field
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()
            gender = columns.Text()

        sync_type(self.conn, User)
        user = User(age=42, name="John", gender="male")
        self.assertEqual(42, user.age)
        self.assertEqual("John", user.name)
        self.assertEqual("male", user.gender)

        # Remove a field
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        sync_type(self.conn, User)
        user = User(age=42, name="John", gender="male")
        with self.assertRaises(AttributeError):
            user.gender

    def test_can_insert_udts(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        class UserModel(Model):
            id = columns.Integer(primary_key=True)
            info = columns.UserDefinedType(User)

        sync_table(self.conn, UserModel)

        user = User(age=42, name="John")
        UserModel.create(self.conn, id=0, info=user)

        self.assertEqual(1, UserModel.objects.count(self.conn))

        john = UserModel.objects().first(self.conn)
        self.assertEqual(0, john.id)
        self.assertTrue(type(john.info) is User)
        self.assertEqual(42, john.info.age)
        self.assertEqual("John", john.info.name)

    def test_can_update_udts(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        class UserModel(Model):
            id = columns.Integer(primary_key=True)
            info = columns.UserDefinedType(User)

        sync_table(self.conn, UserModel)

        user = User(age=42, name="John")
        created_user = UserModel.create(self.conn, id=0, info=user)

        john_info = UserModel.objects().first(self.conn).info
        self.assertEqual(42, john_info.age)
        self.assertEqual("John", john_info.name)

        created_user.info = User(age=22, name="Mary")
        created_user.update(self.conn)

        mary_info = UserModel.objects().first(self.conn).info
        self.assertEqual(22, mary_info.age)
        self.assertEqual("Mary", mary_info.name)

    def test_can_update_udts_with_nones(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        class UserModel(Model):
            id = columns.Integer(primary_key=True)
            info = columns.UserDefinedType(User)

        sync_table(self.conn, UserModel)

        user = User(age=42, name="John")
        created_user = UserModel.create(self.conn, id=0, info=user)

        john_info = UserModel.objects().first(self.conn).info
        self.assertEqual(42, john_info.age)
        self.assertEqual("John", john_info.name)

        created_user.info = None
        created_user.update(self.conn)

        john_info = UserModel.objects().first(self.conn).info
        self.assertIsNone(john_info)

    def test_can_create_same_udt_different_keyspaces(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        sync_type(self.conn, User)

        create_keyspace_simple(self.conn, "simplex", 1)
        sync_type(self.conn, User)
        drop_keyspace(self.conn, "simplex")

    def test_can_insert_partial_udts(self):
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()
            gender = columns.Text()

        class UserModel(Model):
            id = columns.Integer(primary_key=True)
            info = columns.UserDefinedType(User)

        sync_table(self.conn, UserModel)

        user = User(age=42, name="John")
        UserModel.create(self.conn, id=0, info=user)

        john_info = UserModel.objects().first(self.conn).info
        self.assertEqual(42, john_info.age)
        self.assertEqual("John", john_info.name)
        self.assertIsNone(john_info.gender)

        user = User(age=42)
        UserModel.create(self.conn, id=0, info=user)

        john_info = UserModel.objects().first(self.conn).info
        self.assertEqual(42, john_info.age)
        self.assertIsNone(john_info.name)
        self.assertIsNone(john_info.gender)

    def test_can_insert_nested_udts(self):
        class Depth_0(UserType):
            age = columns.Integer()
            name = columns.Text()

        class Depth_1(UserType):
            value = columns.UserDefinedType(Depth_0)

        class Depth_2(UserType):
            value = columns.UserDefinedType(Depth_1)

        class Depth_3(UserType):
            value = columns.UserDefinedType(Depth_2)

        class DepthModel(Model):
            id = columns.Integer(primary_key=True)
            v_0 = columns.UserDefinedType(Depth_0)
            v_1 = columns.UserDefinedType(Depth_1)
            v_2 = columns.UserDefinedType(Depth_2)
            v_3 = columns.UserDefinedType(Depth_3)

        sync_table(self.conn, DepthModel)

        udts = [Depth_0(age=42, name="John")]
        udts.append(Depth_1(value=udts[0]))
        udts.append(Depth_2(value=udts[1]))
        udts.append(Depth_3(value=udts[2]))

        DepthModel.create(self.conn, id=0, v_0=udts[0], v_1=udts[1], v_2=udts[2], v_3=udts[3])
        output = DepthModel.objects().first(self.conn)

        self.assertEqual(udts[0], output.v_0)
        self.assertEqual(udts[1], output.v_1)
        self.assertEqual(udts[2], output.v_2)
        self.assertEqual(udts[3], output.v_3)

    def test_can_insert_udts_withh_nones(self):
        """
        Test for inserting all column types as empty into a UserType as None's

        test_can_insert_udts_with_nones tests that each cqlengine column type can be inserted into a UserType as None's.
        It first creates a UserType that has each cqlengine column type, and a corresponding table/Model. It then creates
        a UserType instance where all the fields are None's and inserts the UserType as an instance of the Model. Finally,
        it verifies that each column read from the UserType from Cassandra is None.

        @since 2.5.0
        @jira_ticket PYTHON-251
        @expected_result The UserType is inserted with each column type, and the resulting read yields None's for each column.

        @test_category data_types:udt
        """

        class AllDatatypes(UserType):
            a = columns.Ascii()
            b = columns.BigInt()
            c = columns.Blob()
            d = columns.Boolean()
            e = columns.DateTime()
            f = columns.Decimal()
            g = columns.Double()
            h = columns.Float()
            i = columns.Inet()
            j = columns.Integer()
            k = columns.Text()
            l = columns.TimeUUID()
            m = columns.UUID()
            n = columns.VarInt()

        class AllDatatypesModel(Model):
            id = columns.Integer(primary_key=True)
            data = columns.UserDefinedType(AllDatatypes)

        sync_table(self.conn, AllDatatypesModel)

        input = AllDatatypes(
            a=None,
            b=None,
            c=None,
            d=None,
            e=None,
            f=None,
            g=None,
            h=None,
            i=None,
            j=None,
            k=None,
            l=None,
            m=None,
            n=None,
        )
        AllDatatypesModel.create(self.conn, id=0, data=input)

        self.assertEqual(1, AllDatatypesModel.objects.count(self.conn))

        output = AllDatatypesModel.objects().first(self.conn).data
        self.assertEqual(input, output)

    def test_can_insert_udts_with_all_datatypes(self):
        """
        Test for inserting all column types into a UserType

        test_can_insert_udts_with_all_datatypes tests that each cqlengine column type can be inserted into a UserType.
        It first creates a UserType that has each cqlengine column type, and a corresponding table/Model. It then creates
        a UserType instance where all the fields have corresponding data, and inserts the UserType as an instance of the Model.
        Finally, it verifies that each column read from the UserType from Cassandra is the same as the input parameters.

        @since 2.5.0
        @jira_ticket PYTHON-251
        @expected_result The UserType is inserted with each column type, and the resulting read yields proper data for each column.

        @test_category data_types:udt
        """

        class AllDatatypes(UserType):
            a = columns.Ascii()
            b = columns.BigInt()
            c = columns.Blob()
            d = columns.Boolean()
            e = columns.DateTime()
            f = columns.Decimal()
            g = columns.Double()
            h = columns.Float()
            i = columns.Inet()
            j = columns.Integer()
            k = columns.Text()
            l = columns.TimeUUID()
            m = columns.UUID()
            n = columns.VarInt()

        class AllDatatypesModel(Model):
            id = columns.Integer(primary_key=True)
            data = columns.UserDefinedType(AllDatatypes)

        sync_table(self.conn, AllDatatypesModel)

        input = AllDatatypes(
            a="ascii",
            b=2 ** 63 - 1,
            c=bytearray(b"hello world"),
            d=True,
            e=datetime.utcfromtimestamp(872835240),
            f=Decimal("12.3E+7"),
            g=2.39,
            h=3.4028234663852886e38,
            i="123.123.123.123",
            j=2147483647,
            k="text",
            l=UUID("FE2B4360-28C6-11E2-81C1-0800200C9A66"),
            m=UUID("067e6162-3b6f-4ae2-a171-2470b63dff00"),
            n=int(str(2147483647) + "000"),
        )
        AllDatatypesModel.create(self.conn, id=0, data=input)

        self.assertEqual(1, AllDatatypesModel.objects.count(self.conn))
        output = AllDatatypesModel.objects().first(self.conn).data

        for i in range(ord("a"), ord("a") + 14):
            self.assertEqual(input[chr(i)], output[chr(i)])

    def test_can_insert_udts_protocol_v4_datatypes(self):
        """
        Test for inserting all protocol v4 column types into a UserType

        test_can_insert_udts_protocol_v4_datatypes tests that each protocol v4 cqlengine column type can be inserted
        into a UserType. It first creates a UserType that has each protocol v4 cqlengine column type, and a corresponding
        table/Model. It then creates a UserType instance where all the fields have corresponding data, and inserts the
        UserType as an instance of the Model. Finally, it verifies that each column read from the UserType from Cassandra
        is the same as the input parameters.

        @since 2.6.0
        @jira_ticket PYTHON-245
        @expected_result The UserType is inserted with each protocol v4 column type, and the resulting read yields proper data for each column.

        @test_category data_types:udt
        """

        if PROTOCOL_VERSION < 4:
            raise unittest.SkipTest(
                "Protocol v4 datatypes in UDTs require native protocol 4+, currently using: {0}".format(
                    PROTOCOL_VERSION
                )
            )

        class Allv4Datatypes(UserType):
            a = columns.Date()
            b = columns.SmallInt()
            c = columns.Time()
            d = columns.TinyInt()

        class Allv4DatatypesModel(Model):
            id = columns.Integer(primary_key=True)
            data = columns.UserDefinedType(Allv4Datatypes)

        sync_table(self.conn, Allv4DatatypesModel)

        input = Allv4Datatypes(
            a=Date(date(1970, 1, 1)), b=32523, c=Time(time(16, 47, 25, 7)), d=123
        )
        Allv4DatatypesModel.create(self.conn, id=0, data=input)

        self.assertEqual(1, Allv4DatatypesModel.objects.count(self.conn))
        output = Allv4DatatypesModel.objects().first(self.conn).data

        for i in range(ord("a"), ord("a") + 3):
            self.assertEqual(input[chr(i)], output[chr(i)])

    def test_nested_udts_inserts(self):
        """
        Test for inserting collections of user types using cql engine.

        test_nested_udts_inserts Constructs a model that contains a list of usertypes. It will then attempt to insert
        them. The expectation is that no exception is thrown during insert. For sanity sake we also validate that our
        input and output values match. This combination of model, and UT produces a syntax error in 2.5.1 due to
        improper quoting around the names collection.

        @since 2.6.0
        @jira_ticket PYTHON-311
        @expected_result No syntax exception thrown

        @test_category data_types:udt
        """

        class Name(UserType):
            type_name__ = "header"

            name = columns.Text()
            value = columns.Text()

        class Container(Model):
            id = columns.UUID(primary_key=True, default=uuid4)
            names = columns.List(columns.UserDefinedType(Name))

        # Construct the objects and insert them
        names = []
        for i in range(0, 10):
            names.append(Name(name="name{0}".format(i), value="value{0}".format(i)))

        # Create table, insert data
        sync_table(self.conn, Container)
        Container.create(self.conn, id=UUID("FE2B4360-28C6-11E2-81C1-0800200C9A66"), names=names)

        # Validate input and output matches
        self.assertEqual(1, Container.objects.count(self.conn))
        names_output = Container.objects().first(self.conn).names
        self.assertEqual(names_output, names)

    def test_udts_with_unicode(self):
        """
        Test for inserting models with unicode and udt columns.

        test_udts_with_unicode constructs a model with a user defined type. It then attempts to insert that model with
        a unicode primary key. It will also attempt to upsert a udt that contains unicode text.

        @since 3.0.0
        @jira_ticket PYTHON-353
        @expected_result No exceptions thrown

        @test_category data_types:udt
        """
        ascii_name = "normal name"
        unicode_name = "Fran\u00E7ois"

        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        class UserModelText(Model):
            id = columns.Text(primary_key=True)
            info = columns.UserDefinedType(User)

        sync_table(self.conn, UserModelText)
        # Two udt instances one with a unicode one with ascii
        user_template_ascii = User(age=25, name=ascii_name)
        user_template_unicode = User(age=25, name=unicode_name)

        UserModelText.create(self.conn, id=ascii_name, info=user_template_unicode)
        UserModelText.create(self.conn, id=unicode_name, info=user_template_ascii)
        UserModelText.create(self.conn, id=unicode_name, info=user_template_unicode)

    def test_db_field_override(self):
        """
        Tests for db_field override

        Tests to ensure that udt's in models can specify db_field for a particular field and that it will be honored.

        @since 3.1.0
        @jira_ticket PYTHON-346
        @expected_result The actual cassandra column will use the db_field specified.

        @test_category data_types:udt
        """

        class db_field_different(UserType):
            age = columns.Integer(db_field="a")
            name = columns.Text(db_field="n")

        class TheModel(Model):
            id = columns.Integer(primary_key=True)
            info = columns.UserDefinedType(db_field_different)

        sync_table(self.conn, TheModel)

        cluster = self.conn.cluster
        type_meta = cluster.metadata.keyspaces[self.conn.keyspace].user_types[
            db_field_different.type_name()
        ]

        type_fields = (db_field_different.age, db_field_different.name)

        self.assertEqual(len(type_meta.field_names), len(type_fields))
        for f in type_fields:
            self.assertIn(f.db_field_name, type_meta.field_names)

        id = 0
        age = 42
        name = "John"
        info = db_field_different(age=age, name=name)
        TheModel.create(self.conn, id=id, info=info)

        self.assertEqual(1, TheModel.objects.count(self.conn))

        john = TheModel.objects().first(self.conn)
        self.assertEqual(john.id, id)
        info = john.info
        self.assertIsInstance(info, db_field_different)
        self.assertEqual(info.age, age)
        self.assertEqual(info.name, name)
        # also excercise the db_Field mapping
        self.assertEqual(info.a, age)
        self.assertEqual(info.n, name)

    def test_db_field_overload(self):
        """
        Tests for db_field UserTypeDefinitionException

        Test so that when we override a model's default field witha  db_field that it errors appropriately

        @since 3.1.0
        @jira_ticket PYTHON-346
        @expected_result Setting a db_field to an existing field causes an exception to occur.

        @test_category data_types:udt
        """

        with self.assertRaises(UserTypeDefinitionException):

            class something_silly(UserType):
                first_col = columns.Integer()
                second_col = columns.Text(db_field="first_col")

        with self.assertRaises(UserTypeDefinitionException):

            class something_silly_2(UserType):
                first_col = columns.Integer(db_field="second_col")
                second_col = columns.Text()

    def test_set_udt_fields(self):
        # PYTHON-502
        class User(UserType):
            age = columns.Integer()
            name = columns.Text()

        u = User()
        u.age = 20
        self.assertEqual(20, u.age)

    def test_default_values(self):
        """
        Test that default types are set on object creation for UDTs

        @since 3.7.0
        @jira_ticket PYTHON-606
        @expected_result Default values should be set.

        @test_category data_types:udt
        """

        class NestedUdt(UserType):

            test_id = columns.UUID(default=uuid4)
            something = columns.Text()
            default_text = columns.Text(default="default text")

        class OuterModel(Model):

            name = columns.Text(primary_key=True)
            first_name = columns.Text()
            nested = columns.List(columns.UserDefinedType(NestedUdt))
            simple = columns.UserDefinedType(NestedUdt)

        sync_table(self.conn, OuterModel)

        t = OuterModel.create(self.conn, name="test1")
        t.nested = [NestedUdt(something="test")]
        t.simple = NestedUdt(something="")
        t.save(self.conn)
        self.assertIsNotNone(t.nested[0].test_id)
        self.assertEqual(t.nested[0].default_text, "default text")
        self.assertIsNotNone(t.simple.test_id)
        self.assertEqual(t.simple.default_text, "default text")
