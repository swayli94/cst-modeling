'''
This is a module containing functions to construct a surface.
The surface is interploted by sections, e.g., airfoils
'''
import os
import copy
import numpy as np

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from cst_modeling.foil import Section
from cst_modeling.foil import cst_foil_fit, transform, rotate, output_foil

class Surface:
    '''
    Surface class, CST surface generated by sections
    '''

    def __init__(self, n_sec=None, n_cst=None, tail=0.0, name='Wing' ,fname=None, nn=1001, ns=101):
        '''
        Initialize the CST surface (upper & lower)
            n_sec:  number of control sections
            n_cst:  number of CST parameters
            tail:   tail thickness (m)
            name:   name of the surface
            fname:  name of control file (not None: read in settings)
            nn:     number of points of upper/lower section
            ns:     number of spanwise points

        Data:
            secs:   list of [Section] class
            surfs:  list of [surf_x, surf_y, surf_z], they are [ns, nn] lists

        Note:
            + x:    flow direction (m)
            + y:    upside (m)
            + z:    spanwise (m) 
            twist:  +z direction (deg)
            chord:  chord length (m)
            thick:  relative maximum thickness
            tail:   absolute tail thickness (m)
        '''
        n_ = max(1, n_sec)
        self.l2d   = n_ == 1
        self.name  = name
        self.n_cst = n_cst
        self.nn    = nn
        self.ns    = ns
        self.secs  = [ Section() for _ in range(n_) ]
        self.surfs = []

        self.split = False

        # Parameters for plot
        self.half_s = 0.5
        self.center = [0.5, 0.5, 0.5]

        if not fname is None:
            self.read_setting(fname, tail=tail)

    @property
    def n_sec(self):
        return len(self.secs)

    def read_setting(self, fname, tail=0.0):
        '''
        Read in Surface layout and CST parameters from file [fname]
        '''
        if not os.path.exists(fname):
            raise Exception(fname+' does not exist for surface read setting')
        
        key_dict = {'Layout:': 1, 'CST_coefs:': 2}

        found_surf = False
        found_key = 0
        with open(fname, 'r') as f:

            for line in f:
                line = line.split()

                if len(line) < 1:
                    continue
                
                if not found_surf and len(line) > 1:
                    if '[Surf]' in line[0] and self.name in line[1]:
                        found_surf = True

                elif found_key == 0:
                    if line[0] in key_dict:
                        found_key = key_dict[line[0]]

                elif found_key == 1:
                    for i in range(self.n_sec):
                        line = f.readline().split()
                        self.secs[i].xLE   = float(line[0])
                        self.secs[i].yLE   = float(line[1])
                        self.secs[i].zLE   = float(line[2])
                        self.secs[i].chord = float(line[3])
                        self.secs[i].twist = float(line[4])
                        self.secs[i].thick = float(line[5])
                        self.secs[i].tail  = tail/self.secs[i].chord

                        if self.l2d:
                            self.secs[i].zLE = 0.0

                    found_key = 0

                elif found_key == 2:
                    for i in range(self.n_sec):
                        line = f.readline()
                        line = f.readline().split()
                        self.secs[i].cst_u = [float(line[i]) for i in range(self.n_cst)]
                        line = f.readline().split()
                        self.secs[i].cst_l = [float(line[i]) for i in range(self.n_cst)]
                    
                    found_key = 0

                else:
                    # Lines that are not relevant
                    pass
        
        print('Read surface [%s] settings'%(self.name))

        # Locate layout center for plot
        x_range = [self.secs[0].xLE, self.secs[0].xLE]
        y_range = [self.secs[0].yLE, self.secs[0].yLE]
        z_range = [self.secs[0].zLE, self.secs[0].zLE]
        for i in range(self.n_sec):
            x_range[0] = min(x_range[0], self.secs[i].xLE)
            x_range[1] = max(x_range[1], self.secs[i].xLE+self.secs[i].chord)
            y_range[0] = min(y_range[0], self.secs[i].yLE)
            y_range[1] = max(y_range[1], self.secs[i].yLE)
            z_range[0] = min(z_range[0], self.secs[i].zLE)
            z_range[1] = max(z_range[1], self.secs[i].zLE)
        
        span = np.array([x_range[1]-x_range[0], y_range[1]-y_range[0], z_range[1]-z_range[0]])
        self.half_s = span.max()/2.0
        self.center[0] = 0.5*(x_range[1]+x_range[0])
        self.center[1] = 0.5*(y_range[1]+y_range[0])
        self.center[2] = 0.5*(z_range[1]+z_range[0])

    def copyfrom(self, other):
        '''
        Copy from another Surface class
        '''
        if not isinstance(other, Surface):
            raise Exception('Can not copy from a non-surface object')

        self.n_sec = other.n_sec
        self.l2d   = other.l2d
        self.name  = other.name
        self.n_cst = other.n_cst
        self.nn    = other.nn
        self.ns    = other.ns
        self.secs  = copy.deepcopy(other.secs)
        self.surfs = copy.deepcopy(other.surfs)

        self.split = other.split

        self.half_s = other.half_s
        self.center = copy.deepcopy(other.center)

    def geo(self, showfoil=False, split=False):
        '''
        Generate surface geometry
            showfoil:   True ~ output name-foil.dat of airfoils
            split:      True ~ generate [surfs] as upper and lower separately
        '''
        for i in range(self.n_sec):
            self.secs[i].foil(nn=self.nn)
            if showfoil:
                output_foil(self.secs[i].xx, self.secs[i].yu, self.secs[i].yl, ID=i, info=True, fname=self.name+'-foil.dat')

        self.split = split
        self.surfs = []

        if self.l2d:
            sec_ = Section()
            sec_.copyfrom(self.secs[0])
            sec_.zLE = 1.0
            surf_1, surf_2 = Surface.section(self.secs[0], sec_, ns=self.ns, split=split)
            self.surfs.append(surf_1)
            if split:
                self.surfs.append(surf_2)
            return

        for i in range(self.n_sec-1):
            surf_1, surf_2 = Surface.section(self.secs[i], self.secs[i+1], ns=self.ns, split=split)
            self.surfs.append(surf_1)
            if split:
                self.surfs.append(surf_2)

    def add_sec(self, z_location=None):
        '''
        Add sections to the surface, the new sections are interploted from current ones
            z_location: list of spanwise location (must within current sections)

        Note: must run before geo() and flip()
        '''
        if self.l2d:
            print('Can not add sections in 2D case')
            return

        # First update current sections
        for i in range(self.n_sec):
            self.secs[i].foil(nn=self.nn)

        for zz in z_location:
            for j in range(self.n_sec-1):
                if (self.secs[j].zLE-zz)*(self.secs[j+1].zLE-zz)<0.0:
                    rr = (zz - self.secs[j].zLE)/(self.secs[j+1].zLE-self.secs[j].zLE)
                    sec_add = interplot_sec(self.secs[j], self.secs[j+1], ratio=abs(rr))
                    self.secs.insert(j+1, sec_add)
                    break

    def flip(self, axis='None', plane='None'):
        '''
        For surfs, and center. (This should be the last action)
            axis:  Turn 90 deg in axis, +X, -X, +Y, -Y, +Z, -Z
            plane: get symmetry by plane, 'XY', 'YZ', 'ZX'
            (can list multiple action in order, split with space)
        '''
        for axis_ in axis.split():
            if '+X' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][2], coef=-1.0)
                    self.surfs[isec][2] = copy.deepcopy(self.surfs[isec][1])
                    self.surfs[isec][1] = copy.deepcopy(temp)

                temp = self.center[2]*1.0
                self.center[2] = self.center[1]*1.0
                self.center[1] = -temp

            if '-X' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][1], coef=-1.0)
                    self.surfs[isec][1] = copy.deepcopy(self.surfs[isec][2])
                    self.surfs[isec][2] = copy.deepcopy(temp)

                temp = self.center[1]*1.0
                self.center[1] = self.center[2]
                self.center[2] = -temp

            if '+Y' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][0], coef=-1.0)
                    self.surfs[isec][0] = copy.deepcopy(self.surfs[isec][2])
                    self.surfs[isec][2] = copy.deepcopy(temp)

                temp = self.center[0]
                self.center[0] = self.center[2]
                self.center[2] = -temp

            if '-Y' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][2], coef=-1.0)
                    self.surfs[isec][2] = copy.deepcopy(self.surfs[isec][0])
                    self.surfs[isec][0] = copy.deepcopy(temp)

                temp = self.center[2]
                self.center[2] = self.center[0]
                self.center[0] = -temp

            if '+Z' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][1], coef=-1.0)
                    self.surfs[isec][1] = copy.deepcopy(self.surfs[isec][0])
                    self.surfs[isec][0] = copy.deepcopy(temp)

                temp = self.center[1]
                self.center[1] = self.center[0]
                self.center[0] = -temp

            if '-Z' in axis_:
                for isec in range(len(self.surfs)):
                    temp = list_mul(self.surfs[isec][0], coef=-1.0)
                    self.surfs[isec][0] = copy.deepcopy(self.surfs[isec][1])
                    self.surfs[isec][1] = copy.deepcopy(temp)

                temp = self.center[0]
                self.center[0] = self.center[1]
                self.center[1] = -temp

        if 'XY' in plane:
            for isec in range(len(self.surfs)):
                self.surfs[isec][2] = list_mul(self.surfs[isec][2], coef=-1.0)
            self.center[2] = - self.center[2]

        if 'YZ' in plane:
            for isec in range(len(self.surfs)):
                self.surfs[isec][0] = list_mul(self.surfs[isec][0], coef=-1.0)
            self.center[0] = - self.center[0]

        if 'ZX' in plane:
            for isec in range(len(self.surfs)):
                self.surfs[isec][1] = list_mul(self.surfs[isec][1], coef=-1.0)
            self.center[1] = - self.center[1]

    def bend(self, start_angle=0.0, end_angle=0.0, leader=None):
        '''
        Bend the section by angle and leader curve. (Bent angle is of x-axis)
            start_angle:    angle of start section
            end_angle:      angle of end section
            leader:         list of leading points

        '''
        


    def output_tecplot(self, fname=None, one_piece=False):
        '''
        Output the surface to *.dat in Tecplot format
            fname:      the name of the file
            one_piece:  True ~ combine the spanwise sections into one piece
        '''
        if fname is None:
            fname = self.name + '.dat'

        n_sec   = 1 if self.l2d else self.n_sec-1
        n_piece = 2*n_sec if self.split else n_sec
        
        with open(fname, 'w') as f:
            f.write('Variables= X  Y  Z \n ')

            if not one_piece:

                for isec in range(n_piece):
                    X = self.surfs[isec][0]
                    Y = self.surfs[isec][1]
                    Z = self.surfs[isec][2]

                    # X[ns][nn], ns => spanwise
                    ns = len(X)
                    nn = len(X[0])

                    if self.split and isec%2==0:
                        f.write('zone T="SecUpp  %d" i= %d j= %d \n'%(isec, nn, ns))
                    elif self.split and isec%2==1:
                        f.write('zone T="SecLow  %d" i= %d j= %d \n'%(isec, nn, ns))
                    else:
                        f.write('zone T="Section %d" i= %d j= %d \n'%(isec, nn, ns))

                    for i in range(ns):
                        for j in range(nn):
                            f.write('  %.9f   %.9f   %.9f\n'%(X[i][j], Y[i][j], Z[i][j]))
                            
            else:
                
                n_part = 2 if self.split else 1
                npoint = n_sec*(self.ns-1) + 1

                for ii in range(n_part):

                    nn = len(self.surfs[0][0][0])
                    if self.split and ii%2==0:
                        f.write('zone T="SecUpp"  i= %d j= %d \n'%(nn, npoint))
                    elif self.split and ii%2==1:
                        f.write('zone T="SecLow"  i= %d j= %d \n'%(nn, npoint))
                    else:
                        f.write('zone T="Section" i= %d j= %d \n'%(nn, npoint))

                    for isec in range(n_piece):
                        X = self.surfs[isec][0]
                        Y = self.surfs[isec][1]
                        Z = self.surfs[isec][2]

                        # X[ns][nn], ns => spanwise
                        ns = len(X)
                        nn = len(X[0])
                        i_add = 0 if isec>=n_piece-2 else 1

                        if self.split and isec%2!=ii:
                            continue
                        else:
                            for i in range(ns-i_add):
                                for j in range(nn):
                                    f.write('  %.9f   %.9f   %.9f\n'%(X[i][j], Y[i][j], Z[i][j]))

    def output_plot3d(self, fname=None):
        '''
        Output the surface to *.grd in plot3d format
            fname: the name of the file
        '''
        if fname is None:
            fname = self.name + '.grd'

        n_sec   = 1 if self.l2d else self.n_sec-1
        n_piece = 2*n_sec if self.split else n_sec

        # X[ns][nn], ns => spanwise
        X = self.surfs[0][0]
        ns = len(X)
        nn = len(X[0])
        
        with open(fname, 'w') as f:
            f.write('%d \n '%(n_piece))     # Number of surfaces
            for isec in range(n_piece):
                f.write('%d %d 1\n '%(nn, ns))

            for isec in range(n_piece):
                X = self.surfs[isec][0]
                ii = 0
                for i in range(ns):
                    for j in range(nn):
                        f.write(' %.9f '%(X[i][j]))
                        ii += 1
                        if ii%3 == 0:
                            f.write(' \n ')

                Y = self.surfs[isec][1]
                ii = 0
                for i in range(ns):
                    for j in range(nn):
                        f.write(' %.9f '%(Y[i][j]))
                        ii += 1
                        if ii%3 == 0:
                            f.write(' \n ')

                Z = self.surfs[isec][2]
                ii = 0
                for i in range(ns):
                    for j in range(nn):
                        f.write(' %.9f '%(Z[i][j]))
                        ii += 1
                        if ii%3 == 0:
                            f.write(' \n ')

    def plot(self, fig_id=1, type='wireframe'):
        '''
        Plot surface
            fig_id: ID of the figure
            type:   wireframe, surface
        '''
        fig = plt.figure(fig_id)
        ax = Axes3D(fig)

        n_plot = self.n_sec-1
        if self.l2d:
            n_plot += 1

        if self.split:
            n_plot = n_plot * 2

        for i in range(n_plot):
            X = np.array(self.surfs[i][0])
            Y = np.array(self.surfs[i][1])
            Z = np.array(self.surfs[i][2])

            if type in 'wireframe':
                ax.plot_wireframe(X, Y, Z)
            else:
                ax.plot_surface(X, Y, Z)

        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_xlim3d(self.center[0]-self.half_s, self.center[0]+self.half_s)
        ax.set_ylim3d(self.center[1]-self.half_s, self.center[1]+self.half_s)
        ax.set_zlim3d(self.center[2]-self.half_s, self.center[2]+self.half_s)
        plt.show()

    @staticmethod
    def section(sec0, sec1, ns=101, kind='S', split=False):
        '''
        Interplot surface section between curves
            sec0, sec1:     Section object [n0]
            ns:             number of spanwise points
            kind (S/L):     interplot method, linear or smooth
            split:          True ~ generate [surfs] as upper and lower separately

        Return: surf_1, surf_2
                [surf_x, surf_y, surf_z] [ns, nn] (list)
                split ~ False: surf_2 is None
        '''
        if not isinstance(sec0, Section) or not isinstance(sec1, Section):
            raise Exception('Interplot surface section, sec0 and sec1 must be section object')
        
        n0 = len(sec0.xx)
        ratio = []
        for i in range(ns):
            if kind in 'Linear':
                tt = 1.0*i/(ns-1.0)
            else:
                tt = 0.5*(1-np.cos(np.pi*i/(ns-1.0)))
            ratio.append(tt)
            
        if not split:
            nn = len(sec0.x)
        else:
            nn = n0
            surf_x2 = np.zeros((ns,nn))
            surf_y2 = np.zeros((ns,nn))
            surf_z2 = np.zeros((ns,nn))

        surf_x1 = np.zeros((ns,nn))
        surf_y1 = np.zeros((ns,nn))
        surf_z1 = np.zeros((ns,nn))
        
        for i in range(ns):
            tt = 1.0*i/(ns-1.0)
            rr = ratio[i]
            chord = (1-tt)*sec0.chord + tt*sec1.chord
            twist = (1-tt)*sec0.twist + tt*sec1.twist
            xLE   = (1-tt)*sec0.xLE   + tt*sec1.xLE
            yLE   = (1-tt)*sec0.yLE   + tt*sec1.yLE

            xx = []
            yu = []
            yl = []
            zz = []
            for j in range(n0):
                xx.append( (1-tt)*sec0.xx[j] + tt*sec1.xx[j] )
                zz.append( (1-tt)*sec0.zLE   + tt*sec1.zLE   )
                yu.append( (1-rr)*sec0.yu[j] + rr*sec1.yu[j] )
                yl.append( (1-rr)*sec0.yl[j] + rr*sec1.yl[j] )

            xx_, yu_, yl_ = transform(xx, yu, yl, scale=chord, rotate=twist, dx=xLE, dy=yLE, proj=True)
            
            if not split:
                x0 = []
                y0 = []
                z0 = []
                for j in range(n0):
                    x0.append(xx_[-1-j])
                    y0.append(yl_[-1-j])
                    z0.append(zz [-1-j])

                for j in range(1,n0):
                    x0.append(xx_[j])
                    y0.append(yu_[j])
                    z0.append(zz [j])

                for j in range(nn):
                    surf_x1[i][j] = x0[j]
                    surf_y1[i][j] = y0[j]
                    surf_z1[i][j] = z0[j]

                surf_1 = [surf_x1.tolist(), surf_y1.tolist(), surf_z1.tolist()]
                surf_2 = None

            else:
                nn = len(sec0.xx)

                for j in range(n0):
                    surf_x1[i][j] = xx_[j]
                    surf_y1[i][j] = yu_[j]
                    surf_z1[i][j] = zz [j]

                for j in range(n0):
                    surf_x2[i][j] = xx_[j]
                    surf_y2[i][j] = yl_[j]
                    surf_z2[i][j] = zz [j]

                surf_1 = [surf_x1.tolist(), surf_y1.tolist(), surf_z1.tolist()]
                surf_2 = [surf_x2.tolist(), surf_y2.tolist(), surf_z2.tolist()]

        return surf_1, surf_2

#TODO: ===========================================
#TODO: Static functions
#TODO: ===========================================
def interplot_sec(sec0, sec1, ratio=0.5):
    '''
    Interplot a section by ratio. CST coefficients are gained by cst_foil_fit.

    Return: sec
    '''
    if not isinstance(sec0, Section) or not isinstance(sec1, Section):
        raise Exception('Interplot section, sec0 and sec1 must be section object')
    
    sec = Section()
    sec.copyfrom(sec0)

    sec.xLE   = (1-ratio)*sec0.xLE   + ratio*sec1.xLE
    sec.yLE   = (1-ratio)*sec0.yLE   + ratio*sec1.yLE
    sec.zLE   = (1-ratio)*sec0.zLE   + ratio*sec1.zLE
    sec.chord = (1-ratio)*sec0.chord + ratio*sec1.chord
    sec.twist = (1-ratio)*sec0.twist + ratio*sec1.twist
    sec.thick = (1-ratio)*sec0.thick + ratio*sec1.thick
    sec.tail  = (1-ratio)*sec0.tail  + ratio*sec1.tail
    sec.RLE   = (1-ratio)*sec0.RLE   + ratio*sec1.RLE

    for i in range(len(sec0.xx)):
        sec.xx[i] = (1-ratio)*sec0.xx[i] + ratio*sec1.xx[i]
        sec.yu[i] = (1-ratio)*sec0.yu[i] + ratio*sec1.yu[i]
        sec.yl[i] = (1-ratio)*sec0.yl[i] + ratio*sec1.yl[i]

    for i in range(len(sec0.x)):
        sec.x[i] = (1-ratio)*sec0.x[i] + ratio*sec1.x[i]
        sec.y[i] = (1-ratio)*sec0.y[i] + ratio*sec1.y[i]
        sec.z[i] = (1-ratio)*sec0.z[i] + ratio*sec1.z[i]

    sec.cst_u, sec.cst_l = cst_foil_fit(sec.xx, sec.yu, sec.xx, sec.yl, n_order=len(sec0.cst_u))

    return sec

def list_mul(list_, coef=1.0):
    '''
    Multiply each element in the list by coef
    '''
    if not isinstance(list_, list):
        print(str(list_))
        raise Exception('Can not use list_mul for a non-list object')
    
    temp = np.array(list_) * coef
    return temp.tolist()
