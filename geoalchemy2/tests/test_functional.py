import unittest
from nose.tools import eq_, ok_, raises

from sqlalchemy import create_engine, MetaData, Column, Integer, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from geoalchemy2 import Geometry
from sqlalchemy.exc import InternalError


engine = create_engine('postgresql://gis:gis@localhost/gis', echo=True)
metadata = MetaData(engine)
Base = declarative_base(metadata=metadata)


class Lake(Base):
    __tablename__ = 'lake'
    id = Column(Integer, primary_key=True)
    geom = Column(Geometry(geometry_type='LINESTRING'))

    def __init__(self, geom):
        self.geom = geom


class Lake_4326(Base):
    __tablename__ = 'lake_4326'
    id = Column(Integer, primary_key=True)
    geom = Column(Geometry(geometry_type='LINESTRING', srid=4326))

    def __init__(self, geom):
        self.geom = geom


session = sessionmaker(bind=engine)()

postgis_version = session.execute(func.postgis_version()).scalar()
if not postgis_version.startswith('2.'):
    # With PostGIS 1.x the AddGeometryColumn and DropGeometryColumn
    # management functions should be used.
    Lake.__table__.c.geom.type.management = True


class InsertionTest(unittest.TestCase):

    def setUp(self):
        metadata.drop_all(checkfirst=True)
        metadata.create_all()

    def tearDown(self):
        session.rollback()
        metadata.drop_all()

    def test_WKT(self):
        from geoalchemy2 import WKBElement
        l = Lake('LINESTRING(0 0,1 1)')
        session.add(l)
        session.flush()
        session.expire(l)
        ok_(isinstance(l.geom, WKBElement))
        wkt = session.execute(l.geom.ST_AsText()).scalar()
        eq_(wkt, 'LINESTRING(0 0,1 1)')

    def test_WKTElement(self):
        from geoalchemy2 import WKTElement, WKBElement
        l = Lake(WKTElement('LINESTRING(0 0,1 1)'))
        session.add(l)
        session.flush()
        session.expire(l)
        ok_(isinstance(l.geom, WKBElement))
        wkt = session.execute(l.geom.ST_AsText()).scalar()
        eq_(wkt, 'LINESTRING(0 0,1 1)')

    def test_srid_preserved(self):
        from geoalchemy2 import WKTElement, WKBElement
        l = Lake_4326(WKTElement('LINESTRING(0 0,1 1)', srid=4326))
        eq_(4326, l.geom.srid)
        session.add(l)
        session.flush()
        session.expire(l)
        recovered_l = session.query(Lake_4326).one()
        eq_(4326, recovered_l.geom.srid)
        eq_(l, recovered_l)


class CallFunctionTest(unittest.TestCase):

    def setUp(self):
        metadata.drop_all(checkfirst=True)
        metadata.create_all()

    def tearDown(self):
        session.rollback()
        metadata.drop_all()

    def _create_one(self):
        l = Lake('LINESTRING(0 0,1 1)')
        session.add(l)
        session.flush()
        return l.id

    def test_ST_GeometryType(self):
        from sqlalchemy.sql import select, func

        lake_id = self._create_one()

        s = select([func.ST_GeometryType(Lake.__table__.c.geom)])
        r1 = session.execute(s).scalar()
        eq_(r1, 'ST_LineString')

        lake = session.query(Lake).get(lake_id)
        r2 = session.execute(lake.geom.ST_GeometryType()).scalar()
        eq_(r2, 'ST_LineString')

        r3 = session.query(Lake.geom.ST_GeometryType()).scalar()
        eq_(r3, 'ST_LineString')

        r4 = session.query(Lake).filter(
            Lake.geom.ST_GeometryType() == 'ST_LineString').one()
        ok_(isinstance(r4, Lake))
        eq_(r4.id, lake_id)

    def test_ST_Buffer(self):
        from sqlalchemy.sql import select, func
        from geoalchemy2 import WKBElement

        lake_id = self._create_one()

        s = select([func.ST_Buffer(Lake.__table__.c.geom, 2)])
        r1 = session.execute(s).scalar()
        ok_(isinstance(r1, WKBElement))

        lake = session.query(Lake).get(lake_id)
        r2 = session.execute(lake.geom.ST_Buffer(2)).scalar()
        ok_(isinstance(r2, WKBElement))

        r3 = session.query(Lake.geom.ST_Buffer(2)).scalar()
        ok_(isinstance(r3, WKBElement))

        ok_(r1.data == r2.data == r3.data)

        r4 = session.query(Lake).filter(
                func.ST_Within('POINT(0 0)', Lake.geom.ST_Buffer(2))).one()
        ok_(isinstance(r4, Lake))
        eq_(r4.id, lake_id)


class CallFunctionTestWithSRID(unittest.TestCase):

    def setUp(self):
        metadata.drop_all(checkfirst=True)
        metadata.create_all()

    def tearDown(self):
        session.rollback()
        metadata.drop_all()

    def _create_one(self):
        from geoalchemy2 import WKTElement
        l = Lake_4326(WKTElement('LINESTRING(0 0,1 1)', srid=4326))
        session.add(l)
        session.flush()
        return l.id

    def test_ST_GeometryType(self):
        from sqlalchemy.sql import select, func

        lake_id = self._create_one()

        s = select([func.ST_GeometryType(Lake_4326.__table__.c.geom)])
        r1 = session.execute(s).scalar()
        eq_(r1, 'ST_LineString')

        lake = session.query(Lake_4326).get(lake_id)
        r2 = session.execute(lake.geom.ST_GeometryType()).scalar()
        eq_(r2, 'ST_LineString')

        r3 = session.query(Lake_4326.geom.ST_GeometryType()).scalar()
        eq_(r3, 'ST_LineString')

        r4 = session.query(Lake_4326).filter(
            Lake_4326.geom.ST_GeometryType() == 'ST_LineString').one()
        ok_(isinstance(r4, Lake_4326))
        eq_(r4.id, lake_id)

    def test_ST_Buffer(self):
        from sqlalchemy.sql import select, func
        from geoalchemy2 import WKBElement, WKTElement

        lake_id = self._create_one()

        s = select([func.ST_Buffer(Lake_4326.__table__.c.geom, 2)])
        r1 = session.execute(s).scalar()
        ok_(isinstance(r1, WKBElement))

        lake = session.query(Lake_4326).get(lake_id)
        r2 = session.execute(lake.geom.ST_Buffer(2)).scalar()
        ok_(isinstance(r2, WKBElement))

        r3 = session.query(Lake_4326.geom.ST_Buffer(2)).scalar()
        ok_(isinstance(r3, WKBElement))

        ok_(r1.data == r2.data == r3.data)

        r4 = session.query(Lake_4326).filter(
                func.ST_Within(WKTElement('POINT(0 0)', srid=4326),
                                          Lake_4326.geom.ST_Buffer(2))).one()
        ok_(isinstance(r4, Lake_4326))
        eq_(r4.id, lake_id)

    @raises(InternalError)
    def test_MixedSRID(self):
        from sqlalchemy.sql import select, func
        from geoalchemy2 import WKBElement

        lake_id = self._create_one()

        r4 = session.query(Lake_4326).filter(
                func.ST_Within('POINT(0 0)',
                                          Lake_4326.geom.ST_Buffer(2))).one()
