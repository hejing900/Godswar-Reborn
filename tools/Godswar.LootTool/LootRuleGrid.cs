using System.Globalization;

namespace Godswar.LootTool;

/// <summary>
/// The editable drop-rule grid. Keeps the DataGridView plumbing out of the main
/// form: index/item/percent/quantity columns stay authoritative here, and the
/// item-name column is always recomputed from the selected item id.
/// </summary>
internal sealed class LootRuleGrid
{
    private const int IndexColumn = 0;
    private const int ItemIdColumn = 1;
    private const int ItemNameColumn = 2;
    private const int PercentColumn = 3;
    private const int MinimumColumn = 4;
    private const int MaximumColumn = 5;
    private const int EnabledColumn = 6;

    private readonly DataGridView _grid;
    private Func<int, string> _describeItem = static _ => string.Empty;
    private bool _suppressChanged;

    public LootRuleGrid(DataGridView grid)
    {
        _grid = grid;
        _grid.AutoGenerateColumns = false;
        _grid.AllowUserToAddRows = false;
        _grid.AllowUserToDeleteRows = false;
        _grid.RowHeadersWidth = 28;
        _grid.SelectionMode = DataGridViewSelectionMode.CellSelect;
        _grid.EditMode = DataGridViewEditMode.EditOnKeystrokeOrF2;
        _grid.Columns.Clear();
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "序号",
            Width = 55,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "物品ID",
            Width = 80,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "物品",
            Width = 260,
            ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "概率%",
            Width = 70,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "最少",
            Width = 55,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "最多",
            Width = 55,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.Columns.Add(new DataGridViewCheckBoxColumn
        {
            HeaderText = "启用",
            Width = 50,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _grid.CellValueChanged += OnCellValueChanged;
        _grid.CurrentCellDirtyStateChanged += OnCurrentCellDirtyStateChanged;
    }

    /// <summary>Raised whenever a cell edit changes persisted content.</summary>
    public event EventHandler? Changed;

    public void SetItemDescriber(Func<int, string> describeItem)
    {
        _describeItem = describeItem;
        RefreshItemNames();
    }

    public bool IsEmpty => _grid.Rows.Count == 0;

    public int RowCount => _grid.Rows.Count;

    /// <summary>Replaces the grid content without raising change events.</summary>
    public void Bind(IReadOnlyList<LootRule> rules)
    {
        _suppressChanged = true;
        try
        {
            _grid.Rows.Clear();
            foreach (var rule in rules)
            {
                var index = _grid.Rows.Add();
                var row = _grid.Rows[index];
                row.Cells[IndexColumn].Value = rule.LootIndex;
                row.Cells[ItemIdColumn].Value = rule.ItemId;
                row.Cells[ItemNameColumn].Value = _describeItem(rule.ItemId);
                row.Cells[PercentColumn].Value = FormatPercent(rule.ChanceBasisPoints);
                row.Cells[MinimumColumn].Value = rule.MinimumQuantity;
                row.Cells[MaximumColumn].Value = rule.MaximumQuantity;
                row.Cells[EnabledColumn].Value = rule.Enabled;
            }
        }
        finally
        {
            _suppressChanged = false;
        }
    }

    /// <summary>Appends an empty rule on the first unused index.</summary>
    public void AddRow(int defaultItemId, int defaultChanceBasisPoints)
    {
        var index = NextFreeIndex();
        if (index < 0)
        {
            throw new LootValidationException("规则序号已用满 0-31，无法再新增。");
        }

        _suppressChanged = true;
        try
        {
            var rowIndex = _grid.Rows.Add();
            var row = _grid.Rows[rowIndex];
            row.Cells[IndexColumn].Value = index;
            row.Cells[ItemIdColumn].Value = defaultItemId;
            row.Cells[ItemNameColumn].Value = _describeItem(defaultItemId);
            row.Cells[PercentColumn].Value = FormatPercent(defaultChanceBasisPoints);
            row.Cells[MinimumColumn].Value = (short)1;
            row.Cells[MaximumColumn].Value = (short)1;
            row.Cells[EnabledColumn].Value = true;
        }
        finally
        {
            _suppressChanged = false;
        }

        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void RemoveSelectedRows()
    {
        if (_grid.SelectedCells.Count == 0 && _grid.SelectedRows.Count == 0)
        {
            return;
        }

        var indexes = new SortedSet<int>();
        foreach (DataGridViewCell cell in _grid.SelectedCells)
        {
            indexes.Add(cell.RowIndex);
        }

        foreach (DataGridViewRow row in _grid.SelectedRows)
        {
            indexes.Add(row.Index);
        }

        _suppressChanged = true;
        try
        {
            foreach (var index in indexes.Reverse())
            {
                _grid.Rows.RemoveAt(index);
            }
        }
        finally
        {
            _suppressChanged = false;
        }

        Changed?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>Sets the item of the current row, used by the item picker.</summary>
    public bool TrySetCurrentRowItem(int itemId)
    {
        var row = _grid.CurrentCell?.OwningRow;
        if (row is null)
        {
            return false;
        }

        row.Cells[ItemIdColumn].Value = itemId;
        row.Cells[ItemNameColumn].Value = _describeItem(itemId);
        Changed?.Invoke(this, EventArgs.Empty);
        return true;
    }

    /// <summary>Multiplies every row's drop chance, clamped to 0.01%-100%.</summary>
    public void MultiplyPercents(double factor)
    {
        _suppressChanged = true;
        try
        {
            foreach (DataGridViewRow row in _grid.Rows)
            {
                var current = ReadPercentOrDefault(row);
                var next = Math.Clamp(current * factor, 0.01d, 100d);
                row.Cells[PercentColumn].Value = FormatPercentValue(next);
            }
        }
        finally
        {
            _suppressChanged = false;
        }

        Changed?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>Overwrites every row's drop chance with one value.</summary>
    public void SetPercents(double percent)
    {
        var clamped = Math.Clamp(percent, 0.01d, 100d);
        _suppressChanged = true;
        try
        {
            foreach (DataGridViewRow row in _grid.Rows)
            {
                row.Cells[PercentColumn].Value = FormatPercentValue(clamped);
            }
        }
        finally
        {
            _suppressChanged = false;
        }

        Changed?.Invoke(this, EventArgs.Empty);
    }

    private static double ReadPercentOrDefault(DataGridViewRow row)
    {
        var text = Convert.ToString(
            row.Cells[PercentColumn].Value,
            CultureInfo.InvariantCulture);
        return double.TryParse(
            text,
            NumberStyles.Float,
            CultureInfo.InvariantCulture,
            out var value)
            ? value
            : 0.01d;
    }

    private static string FormatPercentValue(double percent) =>
        percent.ToString("0.##", CultureInfo.InvariantCulture);

    public int CurrentItemId =>
        _grid.CurrentCell?.OwningRow?.Cells[ItemIdColumn].Value is int value
            ? value
            : 0;

    /// <summary>
    /// Reads the grid back into validated domain values. Throws
    /// <see cref="LootValidationException"/> with an operator-facing message.
    /// </summary>
    public List<LootRuleInput> ReadRules()
    {
        var rules = new List<LootRuleInput>(_grid.Rows.Count);
        foreach (DataGridViewRow row in _grid.Rows)
        {
            var lootIndex = ReadShort(row, IndexColumn, "序号");
            if (lootIndex is < 0 or > 31)
            {
                throw new LootValidationException(
                    $"第 {row.Index + 1} 行：序号必须在 0-31 之间。");
            }

            var itemId = ReadInt(row, ItemIdColumn, "物品ID");
            if (itemId <= 0)
            {
                throw new LootValidationException(
                    $"第 {row.Index + 1} 行：请选择物品。");
            }

            var percent = ReadDouble(row, PercentColumn, "概率%");
            if (percent is <= 0 or > 100)
            {
                throw new LootValidationException(
                    $"第 {row.Index + 1} 行：概率必须在 0.01% 到 100% 之间。");
            }

            var basisPoints = (int)Math.Round(
                percent * 100d,
                MidpointRounding.AwayFromZero);
            basisPoints = Math.Clamp(basisPoints, 1, 10000);

            var minimum = ReadShort(row, MinimumColumn, "最少");
            var maximum = ReadShort(row, MaximumColumn, "最多");
            if (minimum is < 1 or > 255 || maximum is < 1 or > 255)
            {
                throw new LootValidationException(
                    $"第 {row.Index + 1} 行：数量必须在 1-255 之间。");
            }

            if (maximum < minimum)
            {
                throw new LootValidationException(
                    $"第 {row.Index + 1} 行：最多不能小于最少。");
            }

            var enabled = row.Cells[EnabledColumn].Value is true;
            rules.Add(new LootRuleInput(
                lootIndex,
                itemId,
                basisPoints,
                minimum,
                maximum,
                enabled));
        }

        return rules;
    }

    private void OnCurrentCellDirtyStateChanged(object? sender, EventArgs e)
    {
        // Commit checkbox edits immediately so CellValueChanged fires.
        if (_grid.IsCurrentCellDirty)
        {
            _grid.CommitEdit(DataGridViewDataErrorContexts.Commit);
        }
    }

    private void OnCellValueChanged(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0)
        {
            return;
        }

        if (e.ColumnIndex == ItemIdColumn)
        {
            var row = _grid.Rows[e.RowIndex];
            var itemId = row.Cells[ItemIdColumn].Value is int value ? value : 0;
            _suppressChanged = true;
            try
            {
                row.Cells[ItemNameColumn].Value = _describeItem(itemId);
            }
            finally
            {
                _suppressChanged = false;
            }
        }

        if (!_suppressChanged)
        {
            Changed?.Invoke(this, EventArgs.Empty);
        }
    }

    private void RefreshItemNames()
    {
        _suppressChanged = true;
        try
        {
            foreach (DataGridViewRow row in _grid.Rows)
            {
                var itemId = row.Cells[ItemIdColumn].Value is int value ? value : 0;
                row.Cells[ItemNameColumn].Value = _describeItem(itemId);
            }
        }
        finally
        {
            _suppressChanged = false;
        }
    }

    private int NextFreeIndex()
    {
        var used = new HashSet<int>();
        foreach (DataGridViewRow row in _grid.Rows)
        {
            if (row.Cells[IndexColumn].Value is short value)
            {
                used.Add(value);
            }
            else if (int.TryParse(
                         Convert.ToString(
                             row.Cells[IndexColumn].Value,
                             CultureInfo.InvariantCulture),
                         out var parsed))
            {
                used.Add(parsed);
            }
        }

        for (var index = 0; index < 32; index++)
        {
            if (!used.Contains(index))
            {
                return index;
            }
        }

        return -1;
    }

    private static string FormatPercent(int basisPoints) =>
        (basisPoints / 100d).ToString("0.##", CultureInfo.InvariantCulture);

    private static int ReadInt(DataGridViewRow row, int column, string label) =>
        TryRead(row.Cells[column].Value, out var value)
            ? value
            : throw new LootValidationException(
                $"第 {row.Index + 1} 行：{label} 不是整数。");

    private static short ReadShort(DataGridViewRow row, int column, string label)
    {
        if (!TryRead(row.Cells[column].Value, out var value))
        {
            throw new LootValidationException(
                $"第 {row.Index + 1} 行：{label} 不是整数。");
        }

        if (value is < short.MinValue or > short.MaxValue)
        {
            throw new LootValidationException(
                $"第 {row.Index + 1} 行：{label} 超出范围。");
        }

        return (short)value;
    }

    private static double ReadDouble(DataGridViewRow row, int column, string label)
    {
        var text = Convert.ToString(
            row.Cells[column].Value,
            CultureInfo.InvariantCulture);
        if (double.TryParse(
                text,
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out var value))
        {
            return value;
        }

        throw new LootValidationException(
            $"第 {row.Index + 1} 行：{label} 不是数字。");
    }

    private static bool TryRead(object? cellValue, out int value)
    {
        switch (cellValue)
        {
            case short shortValue:
                value = shortValue;
                return true;
            case int intValue:
                value = intValue;
                return true;
            default:
                return int.TryParse(
                    Convert.ToString(cellValue, CultureInfo.InvariantCulture),
                    NumberStyles.Integer,
                    CultureInfo.InvariantCulture,
                    out value);
        }
    }
}
