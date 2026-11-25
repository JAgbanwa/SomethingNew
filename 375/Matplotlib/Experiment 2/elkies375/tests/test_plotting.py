"""Nonempty controls, honest coverage, and exact large-integer display checks."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from equation import check_point, points_from_cube
import campaign
import region
from plotting import (CampaignViewer, completed_intervals, geometry_values,
                      load_snapshot, plot_campaign, real_geometry, verified_points)


def fixture(directory, huge=False):
    directory=Path(directory)
    nlow,nhigh=(10**17,10**20) if huge else (1,13)
    plan=region.make_region(nlow,nhigh,height_max=None if huge else 25)
    width=1000 if huge else 5
    manifest=campaign.ensure_manifest(directory,plan,band_width=width,target="cubes")
    task=(next(region.iter_tasks(plan,width)) if huge else
          [t for t in region.iter_tasks(plan,width) if t.height==25 and t.index_stop==100][0])
    H,left,right=task.height,task.index_start,task.index_stop
    nxt=right-3 if huge else left
    lattice_count="0" if huge else "28"
    row=campaign.empty_task(task)
    row.update(status="partial" if huge else "complete",next_index=str(nxt),
               tiles_count="1",lattice_points=lattice_count,
               points=[] if huge else points_from_cube((20,20,-25)),
               cube_triples=[] if huge else [["20","20","-25"]],
               tiles=[{"height":str(H),"left":str(nxt),"right":str(right),"lattice_points_delta":lattice_count}],
               attempts=[{"index_stop":str(right),"max_tiles":1,"elapsed_seconds":0.0,"status":"validated",
                          "terminal":{"type":"end","complete":not huge,"next_index":str(nxt),"tiles":1,
                                      "lattice_points":lattice_count,"reason":"tile_budget" if huge else "complete"}}])
    campaign.write_json(campaign.task_path(directory,task),row)
    campaign.search_small_heights(directory,plan,primitive=False)
    return row


class PlotChecks(unittest.TestCase):
    def test_exact_n_values_above_float_precision(self):
        values=geometry_values(10**17,10**20,24)
        self.assertEqual(len(values),24)
        self.assertEqual(values[0],10**17)
        self.assertEqual(values[-1],10**20)
        for index,value in enumerate(values):
            target=(10**17)**(23-index)*(10**20)**index
            self.assertLessEqual(value**23,target)
            self.assertGreater((value+1)**23,target)
        self.assertEqual(len(geometry_values(1,1000,257)),257)

    def test_isolated_control_is_present(self):
        import numpy as np
        branches=real_geometry(2)
        isolated=[(q,v) for q,v in branches if len(q)==1]
        self.assertEqual(len(isolated),1)
        self.assertEqual(float(isolated[0][1][0]),0)
        for n in (0,1,2,13,10**20):
            for q,v in real_geometry(n):
                self.assertTrue(np.isfinite(q).all())
                self.assertTrue(np.isfinite(v).all())

    def test_saved_primitive_flag_cannot_create_star(self):
        point=check_point(2,-5,0)
        point["primitive"]=True
        point["cube_gcd"]="1"
        rechecked=verified_points([point],1,13)
        self.assertFalse(rechecked[0]["primitive"])
        self.assertEqual(rechecked[0]["cube_gcd"],"5")
        point["y"]="1"
        with self.assertRaisesRegex(ValueError,"not an exact solution"):
            verified_points([point],1,13)

    def test_small_nonempty_counts_and_render(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            fixture(path)
            snap=load_snapshot(path)
            self.assertEqual(snap["cube_count"],2)
            self.assertEqual(snap["equation_point_count"],2)
            self.assertEqual(snap["primitive_point_count"],0)
            written=plot_campaign(path,geometry_slices=7,save_prefix=path/"view",show=False)
            self.assertEqual(set(written),{"equation-2d","equation-3d","coverage","metadata"})
            for filename in written.values():
                self.assertGreater(Path(filename).stat().st_size,100)
            meta=json.loads(Path(written["metadata"]).read_text())
            self.assertTrue(meta["geometry_is_not_search_coverage"])
            self.assertIn("2",meta["geometry_only_n_values"])

    def test_tiny_coverage_remains_exact_and_manual_point_is_separate(self):
        import matplotlib.pyplot as plt
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            row=fixture(path,huge=True)
            snap=load_snapshot(path)
            span=completed_intervals(snap)[int(row["task"]["height"])][0]
            self.assertEqual(span[1]-span[0],3)
            self.assertLess(span[1]-span[0],int(row["task"]["index_stop"])-int(row["task"]["index_start"]))
            viewer=CampaignViewer(path,geometry_slices=4)
            self.assertIn("Completed width 3 / assigned width 1000",viewer.cov_detail.get_text())
            self.assertEqual(viewer.snapshot["equation_point_count"],0)
            row["status"]="complete"
            saved=next((path/"tasks").glob("*.json"))
            saved.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,"completion|unfinished|complete"):
                load_snapshot(path)
            row["status"]="error"
            row["error"]="fixture continuation failed"
            row["attempts"].append({"index_stop":row["next_index"],"max_tiles":1,
                                    "elapsed_seconds":0.0,"status":"failed","error":row["error"]})
            saved.write_text(json.dumps(row))
            retained=load_snapshot(path)
            self.assertEqual(completed_intervals(retained),completed_intervals(snap))
            self.assertEqual(retained["tiles"],1)
            viewer=CampaignViewer(path,geometry_slices=4)
            self.assertIn("prior coverage retained",viewer.zoom_ax.get_title(loc="left"))
            plt.close("all")
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            fixture(path)
            viewer=CampaignViewer(path,geometry_slices=4)
            before=viewer.snapshot["complete_tasks"]
            viewer.set_n("13")
            viewer.check_x("-144")
            self.assertEqual(viewer.manual[(13,-144)]["status"],"rational")
            self.assertEqual(viewer.snapshot["complete_tasks"],before)
            self.assertEqual(viewer.snapshot["equation_point_count"],2)
            self.assertIn(13,viewer.geometry_n)
            plt.close("all")


if __name__=="__main__":
    unittest.main()
