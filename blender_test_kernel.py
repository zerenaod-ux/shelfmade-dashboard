"""Runs ON KAGGLE (free GPU): TEST of scripted 3D with Blender (Cycles on the GPU). One scene that GROWS beat by beat: bare hill -> path -> trees -> bridge over a river -> houses -> city. Smooth orbiting camera.
Output /kaggle/working/out: scene.mp4, still_*.png, log.txt (seconds per frame)."""
import os, subprocess, time, glob
OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True); LOG = open(OUT + '/log.txt', 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True); return (r.stdout + r.stderr)
t0 = time.time()
log(sh('nvidia-smi -L')[:200])
log(sh('mkdir -p /tmp/bl && cd /tmp/bl && wget -q https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz && tar xf blender-4.2.3-linux-x64.tar.xz && ls')[-300:])
BL = '/tmp/bl/blender-4.2.3-linux-x64/blender'
SCENE = r'''
import bpy, math, random, time
random.seed(4)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W_, H_ = 720, 1280; FPS = 24; END = 288
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W_, H_, 100
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, END
sc.render.engine = 'CYCLES'; sc.cycles.samples = 28; sc.cycles.use_denoising = True
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences; prefs.compute_device_type = 'CUDA'; prefs.get_devices()
    for d in prefs.devices: d.use = True
    sc.cycles.device = 'GPU'
except Exception as e: print('GPU setup failed', e)
def mat(c, rough=0.7, emit=0):
    m = bpy.data.materials.new('m'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1); b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (c[0], c[1], c[2], 1); b.inputs['Emission Strength'].default_value = emit
    return m
def put(obj, m, loc, sca=(1, 1, 1), rot=(0, 0, 0)):
    obj.data.materials.append(m); obj.location = loc; obj.scale = sca; obj.rotation_euler = rot; bpy.ops.object.shade_smooth(); return obj
def cube(m, loc, sca): bpy.ops.mesh.primitive_cube_add(size=1); return put(bpy.context.object, m, loc, sca)
def cyl(m, loc, sca, v=24): bpy.ops.mesh.primitive_cylinder_add(vertices=v); return put(bpy.context.object, m, loc, sca)
def cone(m, loc, sca, v=24): bpy.ops.mesh.primitive_cone_add(vertices=v); return put(bpy.context.object, m, loc, sca)
def sph(m, loc, sca): bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24); return put(bpy.context.object, m, loc, sca)
def grow(parts, frame, dur=16):
    """parts = list of objects; each pops in with a little overshoot at `frame`."""
    for o in parts:
        fin = tuple(o.scale); o.scale = (0.0001, 0.0001, 0.0001); o.keyframe_insert('scale', frame=1)
        o.keyframe_insert('scale', frame=max(1, frame - 1)); o.scale = fin; o.keyframe_insert('scale', frame=frame + dur)
        for fc in o.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'BACK' if k.co[0] == frame + dur else 'CONSTANT'
GRASS, SOIL, WATER, STONE, WOOD = mat((0.25, 0.55, 0.2), .9), mat((0.75, 0.6, 0.38), .9), mat((0.12, 0.45, 0.8), .15), mat((0.6, 0.6, 0.62), .6), mat((0.4, 0.25, 0.12), .8)
# ground + hill (always there: beat 1 = bare hill)
bpy.ops.mesh.primitive_plane_add(size=60); g = bpy.context.object; g.data.materials.append(GRASS)
sph(GRASS, (0, 2, -0.6), (4.2, 4.2, 2.6))
# river across the front + bridge (beat 4)
rv = cube(WATER, (0, -4.0, 0.02), (60, 1.8, 0.04))
br = [cube(STONE, (0, -4.0, 0.35), (2.6, 2.4, 0.18))] + [cube(STONE, (x, y, 0.55), (2.6 if False else 0.12, 0.12, 0.35)) for x in (-1.25, 1.25) for y in (-5.1, -2.9)]
br += [cube(STONE, (0, -5.12, 0.62), (2.6, 0.1, 0.1)), cube(STONE, (0, -2.88, 0.62), (2.6, 0.1, 0.1))]
# path: stones climbing the hill (beat 2)
path = []
for i in range(14):
    t = i / 13.0; y = -2.6 + t * 4.2; x = math.sin(t * 5.0) * 0.9; z = max(0.04, 2.0 * math.sqrt(max(0, 1 - (x / 4.2) ** 2 - ((y - 2) / 4.2) ** 2)) * 1.0 - 0.6 + 0.04) if abs(x) < 4.2 else 0.04
    path.append(cube(SOIL, (x, y, z), (0.55, 0.5, 0.06)))
# trees (beat 3)
trees = []
for i in range(11):
    a = random.uniform(0, 6.28); r = random.uniform(2.8, 7.5); x, y = math.cos(a) * r, math.sin(a) * r * 0.9 + 1
    if abs(y + 4) < 2.2: continue
    s = random.uniform(0.8, 1.4); trees += [cyl(WOOD, (x, y, 0.3 * s), (0.08 * s, 0.08 * s, 0.6 * s), 12), cone(mat((0.1, 0.4 + random.random() * 0.15, 0.15), .8), (x, y, 0.9 * s), (0.4 * s, 0.4 * s, 0.9 * s), 16)]
# houses (beat 5) and city (beat 6)
houses = []
for i, (x, y) in enumerate([(-1.6, 1.4), (1.5, 1.9), (0.2, 3.2), (-1.0, 3.6)]):
    c = (0.9, 0.85 - 0.1 * (i % 2), 0.7); houses += [cube(mat(c, .7), (x, y, 0.4 + 1.0), (0.7, 0.7, 0.55)), cone(mat((0.7, 0.2, 0.15), .7), (x, y, 0.95 + 1.0), (0.62, 0.62, 0.3), 4)]
city = []
for i in range(16):
    x = -8 + (i % 8) * 2.2 + random.uniform(-.3, .3); y = 6 + (i // 8) * 3 + random.uniform(-.4, .4); h = random.uniform(1.5, 5)
    city.append(cube(mat((0.75 + random.random() * .2, 0.78, 0.85), .4), (x, y, h / 2), (0.9, 0.9, h)))
    city.append(cube(mat((1.0, 0.85, 0.4), .3, 3), (x, y - 0.46, h * 0.6), (0.5, 0.02, h * 0.5)))
for parts, f in ((path, 52), (trees, 98), (br, 144), (houses, 190), (city, 236)): grow(parts, f)
# light + sky
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 4.0; sun.angle = 0.1; so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(50), 0, math.radians(35))
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.55, 0.75, 0.98, 1); bg.inputs[1].default_value = 1.2
# camera on an orbiting rig, keyframed + smooth
rig = bpy.data.objects.new('rig', None); sc.collection.objects.link(rig); rig.location = (0, 1.5, 1.0)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); cam.parent = rig; cam.location = (0, -15, 7.5); cam.data.lens = 38; sc.camera = cam
tr = cam.constraints.new('TRACK_TO'); tr.target = rig; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
rig.rotation_euler = (0, 0, math.radians(-28)); rig.keyframe_insert('rotation_euler', frame=1)
rig.rotation_euler = (0, 0, math.radians(28)); rig.keyframe_insert('rotation_euler', frame=END)
cam.location = (0, -15, 7.5); cam.keyframe_insert('location', frame=1); cam.location = (0, -11, 5.5); cam.keyframe_insert('location', frame=END)
for ob in (rig, cam):
    for fc in ob.animation_data.action.fcurves:
        for k in fc.keyframe_points: k.interpolation = 'BEZIER'
import sys
out = sys.argv[sys.argv.index('--') + 1]
for f in (1, 100, 288): pass
sc.render.image_settings.file_format = 'FFMPEG'; sc.render.ffmpeg.format = 'MPEG4'; sc.render.ffmpeg.codec = 'H264'; sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.filepath = out + '/scene_'
t = time.time(); sc.frame_set(1); sc.render.filepath = out + '/still_01.png'; sc.render.image_settings.file_format = 'PNG'; bpy.ops.render.render(write_still=True); print('FRAME_SECONDS', round(time.time() - t, 1), flush=True)
for f in (100, 190, 288):
    sc.frame_set(f); sc.render.filepath = out + '/still_%03d.png' % f; bpy.ops.render.render(write_still=True)
sc.render.image_settings.file_format = 'FFMPEG'; sc.render.ffmpeg.format = 'MPEG4'; sc.render.ffmpeg.codec = 'H264'; sc.render.filepath = out + '/scene.mp4'
bpy.ops.render.render(animation=True); print('ANIM DONE', flush=True)
'''
open('/kaggle/working/scene.py', 'w').write(SCENE)
r = sh(BL + ' -b -P /kaggle/working/scene.py -- ' + OUT + ' 2>&1 | grep -E "FRAME_SECONDS|ANIM DONE|Error|rror|Traceback|GPU|Fra:" | tail -25'); log(r[-2500:])
log('files', sorted(os.listdir(OUT))); open(OUT + '/DONE', 'w').write('ok'); log('ALL DONE', round(time.time() - t0))
