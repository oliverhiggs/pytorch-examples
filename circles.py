"""An example pytorch neural network for learning to classify circular rings of data."""

import math

import matplotlib.pyplot as plt
import matplotlib.colors
import torch
import torch.nn as nn
from matplotlib.colors import ListedColormap
from torch.utils.data import DataLoader, Dataset, random_split


# ? I wonder if this actually solves better in polar coordinate space?
class CircleData(Dataset):
    """Dataset containing data classified as coming from a given radius.

    There are len(radii) categories. Points are generated by randomly selecting
    a radius from the list provided (providing the target category) and randomly
    selecting an angle from 0 to 2pi. The radius is then perterbed slightly and
    points are translated to cartesian coordinates.
    """

    def __init__(self, radii: list[float], n_dpt: int, std=0.1):
        self.cats = torch.randint(len(radii), (n_dpt,))
        pt_radii = torch.tensor(radii)[self.cats] + torch.randn(n_dpt) * std
        angles = torch.rand(n_dpt)
        self.inputs = torch.stack(
            (
                pt_radii * torch.cos(angles * 2 * torch.pi),
                pt_radii * torch.sin(angles * 2 * torch.pi),
            ),
            dim=-1,
        ).to("cuda")
        self.cats = self.cats.to("cuda")
        self.n_dpt = n_dpt

    def __len__(self):
        return self.n_dpt

    def __getitem__(self, i):
        return self.inputs[i], self.cats[i]


def train_loop(dataloader, model, loss_fn, optimizer, verbose=False):
    size = len(dataloader.dataset)
    for i, data in enumerate(dataloader):
        inputs, labels = data
        pred = model(inputs)
        loss = loss_fn(pred, labels)

        # Set all model parameter gradients to zero
        optimizer.zero_grad()
        # Accumulate gradients in the leaf nodes of the model & loss graph
        loss.backward()
        # Use the stored gradients in params and updates according to the
        # optimizer function
        optimizer.step()

        if i % 100 == 0 and verbose:
            loss, current = loss.item(), (i + 1) * len(inputs)
            print(f"Loss: {loss:>7f} [{current:>5d}/{size:>5d}]")


def plot_ax(
    ax,
    x,
    y,
    mesh_pred,
    title,
    trn_dset,
    tst_dset,
    alpha=0.5,
    cols=["r", "b", "g", "c", "m", "y", "k"],
):
    cols = cols[: mesh_pred.shape[1]]
    col_rgb = []
    for col in cols:
        col_rgb.append(matplotlib.colors.to_rgb(col))
    # Create a matrix that maps model outputs to RGB colors
    col_rgb_arr = torch.tensor(col_rgb).T.to("cuda")

    # Map the predictions into the color array
    mesh_cols = torch.matmul(mesh_pred, col_rgb_arr.T)
    ax.pcolormesh(
        x,
        y,
        mesh_cols.reshape(npoints, npoints, -1).detach().cpu().numpy(),
        cmap=ListedColormap(cols),
        alpha=alpha,
    )
    ax.set_title(title)
    add_scatter(ax, trn_dset, "o", cols)
    add_scatter(ax, tst_dset, "x", cols)


def add_scatter(ax, dataset, marker, cols):
    scatter_pt, scatter_col = zip(*[(x, y) for x, y in dataset])
    scatter_pt = torch.stack(scatter_pt).cpu().numpy()
    scatter_col = torch.stack(scatter_col).cpu().numpy()
    ax.scatter(
        scatter_pt[:, 0],
        scatter_pt[:, 1],
        c=scatter_col,
        cmap=ListedColormap(cols[: max(scatter_col) + 1]),
        marker=marker,
    )


radii = [1, 2, 3, 4, 5, 6]
n_cats = len(radii)
dataset = CircleData(radii, 50 * n_cats, std=0.5)
train_dataset, test_dataset = random_split(dataset, [0.8, 0.2])

batch_size = 64
train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=True)

model = nn.Sequential(
    nn.Linear(2, 32),
    nn.ReLU(),
    nn.Linear(32, n_cats),
)
model = model.to("cuda")
n_epochs = 500
learning_rate = 0.1
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)
loss_fn = nn.CrossEntropyLoss().to("cuda")

npoints = 101
ax_length = max(max(radii) * 1.5, max([max(abs(x)) for x, _ in dataset]))
ls = torch.linspace(-ax_length, ax_length, npoints)
x, y = torch.meshgrid(ls, ls, indexing="ij")
mesh = torch.stack((x.ravel(), y.ravel()), axis=1).to("cuda")

epoch_mesh_preds = [nn.Softmax(dim=-1)(model(mesh))]
epochs_to_plot = [0, 10, 20, 50, 100, 500]
for t in range(n_epochs):
    train_loop(train_dataloader, model, loss_fn, optimizer)
    if t + 1 in epochs_to_plot:
        epoch_mesh_preds.append(nn.Softmax(dim=-1)(model(mesh)))

n_ax = len(epochs_to_plot)
n_row = int(n_ax**0.5)
n_col = math.ceil(n_ax / n_row)
fig, axs = plt.subplots(n_row, n_col, figsize=(4 * n_col, 4 * n_row))

for mp, ep, ax in zip(epoch_mesh_preds, epochs_to_plot, axs.ravel()):
    plot_ax(ax, x, y, mp, f"Epoch {ep}", train_dataset, test_dataset)

plt.show()
