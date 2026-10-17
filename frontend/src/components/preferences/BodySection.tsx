import { useEffect, useState } from 'react';
import { Box, InputAdornment, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import LocalFireDepartment from '@mui/icons-material/LocalFireDepartment';
import { Section } from './PreferenceFields';
import { BODY_DEFAULTS, BODY_RANGE, type BodySetting, type Sex } from '../../preferences/model';

const parse = (text: string) => Number(text.replace(',', '.'));

/** Whole number field: empty = not given (`null`); a value out of range is not saved. */
function NumberField({
  label,
  unit,
  value,
  range,
  placeholder,
  onChange,
}: {
  label: string;
  unit: string;
  value: number | null;
  range: readonly [number, number];
  placeholder: number;
  onChange: (v: number | null) => void;
}) {
  const [text, setText] = useState(value === null ? '' : String(value));
  const typed = parse(text);
  const invalid = text !== '' && (Number.isNaN(typed) || typed < range[0] || typed > range[1]);

  // Keep the text in sync when the value changes from outside (e.g. "restore defaults").
  useEffect(() => {
    if (value === null ? text !== '' && !invalid : typed !== value) setText(value === null ? '' : String(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <TextField
      size="small"
      label={label}
      value={text}
      placeholder={String(placeholder)}
      error={invalid}
      helperText={invalid ? `${range[0]}–${range[1]} ${unit}` : ' '}
      onChange={(e) => {
        setText(e.target.value);
        const v = parse(e.target.value);
        if (e.target.value === '') onChange(null);
        else if (!Number.isNaN(v) && v >= range[0] && v <= range[1]) onChange(Math.round(v));
      }}
      slotProps={{
        htmlInput: { inputMode: 'numeric' },
        input: { endAdornment: <InputAdornment position="end">{unit}</InputAdornment> },
      }}
    />
  );
}

/** Body data for the calorie estimate (Preferences page only; it stays on the device). */
export default function BodySection({ value, onChange }: { value: BodySetting; onChange: (v: BodySetting) => void }) {
  return (
    <Section
      icon={<LocalFireDepartment />}
      title="Kalorie"
      hint="Dzięki tym danym policzymy, ile kalorii naprawdę spalisz w drodze. Zostają tylko na tym urządzeniu."
    >
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, mb: 0.5 }}>
        <NumberField
          label="Waga"
          unit="kg"
          value={value.weightKg}
          range={BODY_RANGE.weightKg}
          placeholder={BODY_DEFAULTS.weightKg}
          onChange={(weightKg) => onChange({ ...value, weightKg })}
        />
        <NumberField
          label="Wzrost"
          unit="cm"
          value={value.heightCm}
          range={BODY_RANGE.heightCm}
          placeholder={BODY_DEFAULTS.heightCm}
          onChange={(heightCm) => onChange({ ...value, heightCm })}
        />
        <NumberField
          label="Wiek"
          unit="lat"
          value={value.age}
          range={BODY_RANGE.age}
          placeholder={BODY_DEFAULTS.age}
          onChange={(age) => onChange({ ...value, age })}
        />
      </Box>
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        aria-label="Płeć"
        value={value.sex}
        onChange={(_, sex: Sex | null) => onChange({ ...value, sex })}
        sx={{ '& .MuiToggleButton-root': { textTransform: 'none' }, '& .Mui-selected': { fontWeight: 700 } }}
      >
        <ToggleButton value="female">Kobieta</ToggleButton>
        <ToggleButton value="male">Mężczyzna</ToggleButton>
      </ToggleButtonGroup>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Pokazujemy kalorie netto, czyli ponad to, co spalasz w spoczynku. Dla pustych pól przyjmujemy typowe wartości
        ({BODY_DEFAULTS.weightKg} kg, {BODY_DEFAULTS.heightCm} cm, {BODY_DEFAULTS.age} lat). To szacunek dla płaskiego
        terenu, bez bagażu i bez podjazdów.
      </Typography>
    </Section>
  );
}
