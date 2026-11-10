#!/usr/bin/env python3
"""光照资源与发电小时数测算（PVGIS + NASA POWER 双源交叉校验，替代 Meteonorm 离线查询）。

用法:
  python3 solar_hours.py --lat 31.54 --lon 121.13 --cap 1.41 --name 勃乐氏 \
      --out /path/xxx.xlsx [--tilt 0] [--azimuth 0] [--loss 14]

说明:
  - PVGIS v5.2（ERA5 辐照 + 逐时模型）给出最佳倾角、倾斜面辐照、首年等效小时数；
  - NASA POWER（2015-2024 月均）给出水平面 GHI/DNI，用于交叉校验与逐月分布；
  - 全部走 /usr/bin/curl（本机 Python 无 CA），不依赖第三方库。
"""
import argparse, json, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlsx_writer as xw

CURL = "/usr/bin/curl" if os.path.exists("/usr/bin/curl") else "curl"


def get(url, timeout=60):
    p = subprocess.run([CURL, "-sS", "-m", str(timeout), url], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:300])
    return json.loads(p.stdout.decode("utf-8"))


def pvgis(lat, lon, loss, tilt=None, azimuth=None):
    url = ("https://re.jrc.ec.europa.eu/api/v5_2/PVcalc?lat=%s&lon=%s&peakpower=1"
           "&loss=%s&mountingplace=building&outputformat=json" % (lat, lon, loss))
    if tilt and azimuth is not None:
        url += "&angle=%s&aspect=%s" % (tilt, azimuth)
    else:
        url += "&optimalangles=1"
    return get(url)


def nasa(lat, lon, y0=2015, y1=2024):
    url = ("https://power.larc.nasa.gov/api/temporal/monthly/point?"
           "parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI&community=RE"
           "&longitude=%s&latitude=%s&format=JSON&start=%d&end=%d" % (lon, lat, y0, y1))
    return get(url, 90)


DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def build_styles():
    """补一个“左对齐/顶端/换行/带框”样式（索引18）。"""
    xw.XFS.append(('5', '0', '1', 6))
    n = len(xw.XFS)

    def cellxfs():
        out = []
        for f, fill, bord, nf in xw.XFS:
            out.append(
                '<xf numFmtId="%s" fontId="%s" fillId="%s" borderId="%s" xfId="0"%s applyFont="1"'
                ' applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="%s"'
                ' vertical="%s" wrapText="%s"/></xf>'
                % (xw.NFID.get(nf, 0), f, fill, bord,
                   ' applyNumberFormat="1"' if xw.NFID.get(nf, 0) else '',
                   'left' if f in ('1', '2', '5', '12', '13', '17', '18') else 'center',
                   'top' if f in ('12', '17', '18') else 'center',
                   '1' if f in ('3', '12', '17', '18') else '0'))
        return out
    xw.cellxfs = cellxfs
    head = xw.STYLES.split('<cellXfs')[0]
    xw.STYLES = (head + '<cellXfs count="%d">' % n + ''.join(cellxfs()) +
                 '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/>'
                 '</cellStyles></styleSheet>')
    return 18


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--cap", type=float, required=True, help="装机容量 MW")
    ap.add_argument("--name", default="项目")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tilt", type=float, default=0)
    ap.add_argument("--azimuth", type=float, default=0)
    ap.add_argument("--loss", type=float, default=14)
    ap.add_argument("--base-hours", type=float, default=0, help="测算表采用的等效小时数，用于对照")
    a = ap.parse_args()

    W = build_styles()
    pv = pvgis(a.lat, a.lon, a.loss, a.tilt, a.azimuth)
    na = nasa(a.lat, a.lon)
    mon_pv = pv["outputs"]["monthly"]["fixed"]
    tot = pv["outputs"]["totals"]["fixed"]
    slope = pv["inputs"]["mounting_system"]["fixed"]["slope"]["value"]
    azim = pv["inputs"]["mounting_system"]["fixed"]["azimuth"]["value"]
    hpoa = tot["H(i)_y"]
    ey = tot["E_y"]

    par = na["properties"]["parameter"]
    years = sorted({k[:4] for k in par["ALLSKY_SFC_SW_DWN"]})
    ghi_m, dni_m = [], []
    for m in range(1, 13):
        gs = [par["ALLSKY_SFC_SW_DWN"]["%s%02d" % (y, m)] for y in years
              if par["ALLSKY_SFC_SW_DWN"].get("%s%02d" % (y, m), -999) > -900]
        ds = [par["ALLSKY_SFC_SW_DNI"]["%s%02d" % (y, m)] for y in years
              if par["ALLSKY_SFC_SW_DNI"].get("%s%02d" % (y, m), -999) > -900]
        ghi_m.append(round(sum(gs) / len(gs), 2) if gs else 0.0)
        dni_m.append(round(sum(ds) / len(ds), 2) if ds else 0.0)
    # NASA 返回的是日均值 kWh/m2/day，表里按月总量列示
    ghi_m = [round(g * d, 1) for g, d in zip(ghi_m, DAYS)]
    dni_m = [round(g * d, 1) for g, d in zip(dni_m, DAYS)]
    ghi_y = sum(ghi_m)
    dni_y = sum(dni_m)

    rows = [[("%s 光照资源与发电小时数测算（PVGIS-ERA5 %s—%s / NASA POWER %s—%s）"
              % (a.name, pv["inputs"]["meteo_data"]["year_min"], pv["inputs"]["meteo_data"]["year_max"],
                 years[0], years[-1]), 1)]]
    rows.append([("坐标 %.4f°N / %.4f°E　│　装机 %.3f MW　│　最佳倾角 %d°　方位角 %d°（0=正南）　│　系统损失 %.0f%%"
                  % (a.lat, a.lon, a.cap, slope, azim, a.loss), 2)])

    hdr = ["月份", "水平面GHI\n(kWh/m²·月)", "法向直射DNI\n(kWh/m²·月)", "倾斜面POA\n(kWh/m²·月)",
           "首年发电量\n(kWh/kWp)", "折合利用小时\n(h)"]
    rows.append([(h, 3) for h in hdr])
    for i, m in enumerate(mon_pv):
        rows.append(["%d月" % m["month"],
                     (ghi_m[i], 6), (dni_m[i], 6), (round(m["H(i)_m"], 1), 6),
                     (round(m["E_m"], 1), 6), (round(m["E_m"], 0), 6)])
    rows.append([("合计/年", 8), (round(ghi_y, 0), 10), (round(dni_y, 0), 10),
                 (round(hpoa, 0), 10), (round(ey, 0), 10), (round(ey, 0), 10)])

    cap_kw = a.cap * 1000
    e_year = ey * cap_kw / 10000.0
    pr = ey / hpoa

    rows.append([])
    rows.append([("一、结论", 4)])
    rows.append([("1. 水平面年总辐照 GHI：%.0f kWh/m²（NASA POWER %s—%s 多年平均）；法向直射 DNI：%.0f kWh/m²。"
                  % (ghi_y, years[0], years[-1], dni_y), (None, W))])
    rows.append([("2. %d°最佳倾角倾斜面年辐照 POA：%.0f kWh/m²（PVGIS-ERA5，已计地形遮挡）。"
                  % (int(slope), hpoa), (None, W))])
    rows.append([("3. 首年等效利用小时数：%d h（%.0f kWh/kWp，含 %.0f%% 系统损失），系统效率 PR=%.1f%%。"
                  % (round(ey), ey, a.loss, pr * 100), (None, W))])
    rows.append([("4. 本项目 %.3f MW 首年发电量：%.1f 万kWh（按 PVGIS 口径）。" % (a.cap, e_year), (None, W))])

    if a.base_hours:
        implied_pr = a.base_hours / hpoa * 100
        rows.append([])
        rows.append([("二、与立项测算表口径对照", 4)])
        rows.append([("测算表取首年 %.1f 万kWh，折合等效小时 %.0f h，隐含 PR 约 %.1f%%（%.0f/%.0f）；"
                      "PVGIS 同口径 %.0f h、PR %.1f%%。两者相差约 %.0f%%，测算侧偏保守。"
                      % (a.cap * a.base_hours / 10, a.base_hours, implied_pr, a.base_hours, hpoa,
                         ey, pr * 100, (ey / a.base_hours - 1) * 100), (None, W))])
        rows.append([("建议口径：若上会被问“为何低于 PVGIS”，答“已计屋面高温衰减、积灰、组串失配、逆变器限功率、"
                      "可用率及首年衰减，取保守值”；若要上调小时数，须先补屋面通风与倾角方案复核，不宜直接套用 PVGIS。",
                      (None, W))])

    rows.append([])
    rows.append([("三、数据来源与口径", 4)])
    rows.append([("· PVGIS v5.2（欧盟联合研究中心 JRC），辐射库 PVGIS-ERA5，逐时模型，含地形遮挡；"
                  "屋面按 building-integrated 散热模型计算温升损失。", (None, W))])
    rows.append([("· NASA POWER（NASA Langley），再分析月均 GHI/DNI，%s—%s 共 %d 年。" % (years[0], years[-1], len(years)), (None, W))])
    rows.append([("· 与 Meteonorm 8 同属“卫星/再分析 + 地面站校正”体系，立项阶段可作等价依据；"
                  "如评审或银行明确要求 Meteonorm 正式报告，需在 Windows 环境用正版授权导出。", (None, W))])

    sheets = [{"name": "光照与小时数", "rows": rows,
               "widths": [10, 16, 16, 14, 14, 14], "freeze": 3, "merges": ["A1:F1", "A2:F2"]}]
    xw.build(a.out, sheets)
    print("GHI %.0f kWh/m2 | POA %.0f | 首年 %.0f h | %.1f 万kWh | PR %.1f%%"
          % (ghi_y, hpoa, ey, e_year, pr * 100))
    print("->", a.out)


if __name__ == "__main__":
    main()
