import os, hashlib
import time
from functools import partial
import numpy as np
import pytest
import MDAnalysis as mda
import chiLife
import networkx as nx

pdbids = ["1ubq", "1a2w", '1az5']
ubq = chiLife.fetch("1ubq")
resis = [
    (key, -90, 160)
    for key in chiLife.dihedral_defs
    if key
    not in (chiLife.SUPPORTED_LABELS +
            ("R1B", "R1C", "CYR1", "MTN", "ALA", "GLY") +
            tuple(chiLife.USER_LABELS) +
            tuple(chiLife.USER_dLABELS))
]
ICs = chiLife.get_internal_coords(ubq)
gd_kwargs = [
    {"resi": 28, "atom_list": ["C", "N", "CA", "C"]},
    {"resi": 28, "atom_list": [["C", "N", "CA", "C"], ["N", "CA", "C", "N"]]},
]
gd_ans = [-1.1540443794802524, np.array([-1.15404438, -0.66532042])]


@pytest.mark.parametrize("res", resis)
def test_read_dunbrack(res):
    res, phi, psi = res

    dlib = chiLife.read_bbdep(res, -70, 90)

    dlib_mx, dlib_ori = chiLife.global_mx(*np.squeeze(dlib["coords"][0, :3]))
    dlib["coords"] = np.einsum("ijk,kl->ijl", dlib["coords"], dlib_mx) + dlib_ori


    with np.load(f"test_data/{res}_{phi}_{psi}.npz", allow_pickle=True) as f:
        dlib_ans = {key: f[key] for key in f if key != "allow_pickle"}

    for key in dlib_ans:
        if dlib_ans[key].dtype not in [np.dtype(f"<U{i}") for i in range(1, 5)]:
            np.testing.assert_almost_equal(dlib_ans[key], dlib[key])
        else:
            assert np.all(np.char.equal(dlib_ans[key], dlib[key]))


@pytest.mark.parametrize("pdbid", pdbids)
def test_get_internal_coordinates(pdbid):
    protein = chiLife.fetch(pdbid).select_atoms("protein and not altloc B")

    t1 = time.perf_counter()
    ICs = chiLife.get_internal_coords(protein)
    print(time.perf_counter() - t1)

    np.testing.assert_almost_equal(ICs.coords, protein.atoms.positions, decimal=4)


def test_icset_dihedral():
    ICs = chiLife.get_internal_coords(ubq)
    ICs.set_dihedral(
        [-np.pi / 2, np.pi / 2], 72, [["C", "N", "CA", "C"], ["N", "CA", "C", "N"]]
    )

    ans = mda.Universe("test_data/1ubq.pdb")

    np.testing.assert_almost_equal(ans.atoms.positions, ICs.coords, decimal=3)


def test_sort_pdb():
    pdbfile = "test_data/trt.pdb"
    x = chiLife.sort_pdb(pdbfile)
    with open("test_data/trt_tmp.pdb", "w") as f:
        for line in x:
            f.write(line)

    with open("test_data/trt_tmp.pdb", "r") as f:
        test = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    with open("test_data/trt_sorted.pdb", "r") as f:
        ans = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    os.remove("test_data/trt_tmp.pdb")
    assert test == ans


def test_sort_pdb2():
    x = chiLife.sort_pdb("test_data/GR1G.pdb")

    with open("test_data/GR1G_tmp.pdb", "w") as f:
        for line in x:
            f.write(line)

    with open("test_data/GR1G_tmp.pdb", "rb") as f:
        test = hashlib.md5(f.read()).hexdigest()

    os.remove("test_data/GR1G_tmp.pdb")


def test_sort_pdb3():
    x = chiLife.sort_pdb("test_data/SL_GGAGG.pdb")

    with open("test_data/SL_GGAGG_tmp.pdb", "w") as f:
        for line in x:
            f.write(line)

    U = mda.Universe("test_data/SL_GGAGG_tmp.pdb", in_memory=True)
    os.remove("test_data/SL_GGAGG_tmp.pdb")
    ICs = chiLife.get_internal_coords(U, preferred_dihedrals=[["C", "N", "CA", "C"]])


def test_sort_manymodels():
    x = chiLife.sort_pdb("test_data/msort.pdb")
    with open("test_data/msort_tmp.pdb", "w") as f:
        for i, struct in enumerate(x):
            f.write(f"MODEL {i}\n")
            f.writelines(struct)
            f.write("ENDMDL\n")

    with open("test_data/msort_tmp.pdb", "r") as f:
        test = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    with open("test_data/msort_ans.pdb", "r") as f:
        ans = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    os.remove("test_data/msort_tmp.pdb")

    assert test == ans

def test_makeics():
    traj = mda.Universe("test_data/msort_ans.pdb")
    ICs = [chiLife.get_internal_coords(traj) for ts in traj.universe.trajectory]

    print("d")


def test_mutate():
    protein = chiLife.fetch("1ubq").select_atoms("protein")
    SL = chiLife.SpinLabel(
        "R1C",
        site=28,
        protein=protein,
        energy_func=partial(chiLife.get_lj_rep, forgive=0.8),
    )

    labeled_protein = chiLife.mutate(protein, SL)
    ub1_A28R1 = mda.Universe("test_data/1ubq_A28R1.pdb")

    np.testing.assert_almost_equal(
        ub1_A28R1.atoms.positions, labeled_protein.atoms.positions, decimal=3
    )


def test_mutate2():
    protein = chiLife.fetch("1ubq").select_atoms("protein")
    SL1 = chiLife.SpinLabel(
        "R1C",
        site=28,
        protein=protein,
        energy_func=partial(chiLife.get_lj_rep, forgive=0.8),
    )
    SL2 = chiLife.SpinLabel(
        "R1C",
        site=48,
        protein=protein,
        energy_func=partial(chiLife.get_lj_rep, forgive=0.8),
    )

    labeled_protein = chiLife.mutate(protein, SL1, SL2)
    ub1_A28R1_K48R1 = mda.Universe("test_data/ub1_A28R1_K48R1.pdb")
    np.testing.assert_almost_equal(
        ub1_A28R1_K48R1.atoms.positions, labeled_protein.atoms.positions, decimal=3
    )


def test_mutate3():
    protein = mda.Universe("test_data/1omp_H.pdb").select_atoms("protein")
    SL1 = chiLife.SpinLabel("R1C", site=238, protein=protein, use_H=True)
    SL2 = chiLife.SpinLabel("R1C", site=311, protein=protein, use_H=True)

    labeled_protein = chiLife.mutate(protein, SL1, SL2)
    assert len(labeled_protein.atoms) != len(protein.atoms)


def test_mutate4():
    protein = mda.Universe("test_data/1omp_H.pdb").select_atoms("protein")
    D41G = chiLife.RotamerLibrary("GLY", 41, protein=protein)
    S238A = chiLife.RotamerLibrary("ALA", 238, protein=protein)
    mPro = chiLife.mutate(protein, D41G, S238A, add_missing_atoms=False)
    D41G_pos = mPro.select_atoms("resnum 41").positions
    S238A_pos = mPro.select_atoms("resnum 238").positions
    np.testing.assert_almost_equal(D41G._coords[0], D41G_pos, decimal=6)
    np.testing.assert_almost_equal(S238A._coords[0], S238A_pos, decimal=6)


@pytest.mark.parametrize(["inp", "ans"], zip(gd_kwargs, gd_ans))
def test_get_dihedral(inp, ans):
    dihedral = ICs.get_dihedral(**inp)
    np.testing.assert_almost_equal(dihedral, ans)


def test_ProteinIC_save_pdb():
    protein = mda.Universe("test_data/alphabetical_peptide.pdb").select_atoms("protein")

    uni_ics = chiLife.get_internal_coords(protein)
    uni_ics.save_pdb("test_data/postwrite_alphabet_peptide.pdb")

    with open("test_data/postwrite_alphabet_peptide.pdb", "r") as f:
        test = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    with open("test_data/alphabetical_peptide.pdb", "r") as f:
        truth = hashlib.md5(f.read().encode("utf-8")).hexdigest()

    os.remove("test_data/postwrite_alphabet_peptide.pdb")
    assert test == truth


def test_ic_to_site():
    backbone = ubq.select_atoms("resnum 28 and name N CA C").positions
    r1c = mda.Universe("../chiLife/data/rotamer_libraries/residue_pdbs/R1C.pdb")
    R1ic = chiLife.get_internal_coords(r1c)
    R1ic.to_site(*backbone)

    np.testing.assert_almost_equal(R1ic.coords[1], backbone[1])


def test_has_clashes():
    assert not ICs.has_clashes()
    ICs.set_dihedral(np.pi / 2, 35, ["N", "CA", "C", "N"])
    assert ICs.has_clashes()


def test_add_missing_atoms():
    protein = chiLife.fetch("1omp").select_atoms("protein")
    new_prot = chiLife.mutate(protein)
    assert len(new_prot.atoms) != len(protein.atoms)
    assert len(new_prot.atoms) == 2877


def test_polypro_IC():
    polypro = mda.Universe("test_data/PPII_Capped.pdb")
    polyproIC = chiLife.get_internal_coords(polypro)


@pytest.mark.parametrize(
    "res", set(chiLife.dihedral_defs.keys()) -
           {"CYR1", "MTN", "R1M", "R1C"} -
           chiLife.USER_dLABELS -
           chiLife.USER_LABELS
)
def test_sort_and_internal_coords(res):
    pdbfile = chiLife.DATA_DIR / f"residue_pdbs/{res.lower()}.pdb"
    lines = chiLife.sort_pdb(str(pdbfile))
    anames = [line[13:16] for line in lines if "H" not in line[12:16]]

    with open(pdbfile, "r") as f:
        ans = [
            line[13:16]
            for line in f.readlines()
            if line.startswith("ATOM")
            if "H" not in line[12:16]
        ]

    assert anames == ans


def test_PRO_ics():
    pro = mda.Universe("../chiLife/data/rotamer_libraries/residue_pdbs/pro.pdb")
    pro_ic = chiLife.get_internal_coords(pro)
    assert ("CD", "CG", "CB", "CA") in pro_ic.ICs[1][1]


def test_ProteinIC_set_coords():
    R1A = mda.Universe("../chiLife/data/rotamer_libraries/residue_pdbs/R1A.pdb")
    R1A_IC = chiLife.get_internal_coords(R1A)
    R1A_IC_c = R1A_IC.copy()
    R1A_IC_c.set_dihedral([np.pi/2, -np.pi/2, np.pi/2], 1, [['N', 'CA', 'CB', 'SG' ],
                                                            ['CA', 'CB', 'SG', 'SD'],
                                                            ['CB', 'SG', 'SD', 'CE']])

    coords = R1A_IC_c.coords

    R1A_IC.coords = coords
    np.testing.assert_allclose(R1A_IC.zmats[1], R1A_IC_c.zmats[1], rtol=1e-6)
    np.testing.assert_almost_equal(R1A_IC.coords, R1A_IC_c.coords, decimal=6)


def test_preferred_dihedrals():
    dih = [['N', 'CA', 'CB', 'CB2'],
           ['CA', 'CB', 'CB2', 'CG'],
           ['ND', 'CE3', 'CZ3', 'C31'],
           ['CZ1', 'C11', 'C12', 'N12'],
           ['C11', 'C12', 'N12', 'C13'],
           ['C12', 'N12', 'C13', 'C14'],
           ['N12', 'C13', 'C14', 'C15']]

    TEP = mda.Universe('test_data/TEP.pdb')
    IC = chiLife.get_internal_coords(TEP, resname='TEP', preferred_dihedrals=dih)
    IC2 = chiLife.get_internal_coords(TEP, resname='TEP')

    IC.get_dihedral(1, dih)
    with pytest.raises(ValueError):
        IC2.get_dihedral(1, dih)