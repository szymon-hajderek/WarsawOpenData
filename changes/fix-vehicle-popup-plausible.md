# fix/vehicle-popup-plausible

- The vehicle window opens by itself only when the best match is plausible: top-1 RMSE <= 120 m
  (`PLAUSIBLE_MAX_RMSE_M`). The backend always returns the 4 nearest vehicles with no distance cut-off, so before
  this the sheet opened for vehicles hundreds of metres away. The bus button still opens it on demand.
