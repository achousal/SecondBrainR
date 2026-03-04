function Table(tbl)
  local ncols = #tbl.colspecs
  if ncols == 2 then
    tbl.colspecs[1] = {tbl.colspecs[1][1], 0.25}
    tbl.colspecs[2] = {tbl.colspecs[2][1], 0.75}
  else
    local width = 1.0 / ncols
    for i, colspec in ipairs(tbl.colspecs) do
      tbl.colspecs[i] = {colspec[1], width}
    end
  end
  return tbl
end
