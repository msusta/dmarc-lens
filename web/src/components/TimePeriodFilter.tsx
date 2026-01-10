import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Refresh } from '@mui/icons-material';

export interface TimePeriod {
  preset: string;
  startDate?: Date;
  endDate?: Date;
}

interface TimePeriodFilterProps {
  value: TimePeriod;
  onChange: (period: TimePeriod) => void;
  onRefresh?: () => void;
}

const TimePeriodFilter: React.FC<TimePeriodFilterProps> = ({
  value,
  onChange,
  onRefresh,
}) => {
  const handlePresetChange = (preset: string) => {
    const now = new Date();
    let startDate: Date | undefined;
    let endDate: Date | undefined = now;

    switch (preset) {
      case 'last7days':
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'last30days':
        startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case 'last90days':
        startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        break;
      case 'custom':
        startDate = value.startDate;
        endDate = value.endDate;
        break;
      default:
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    }

    onChange({ preset, startDate, endDate });
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 3, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Time Period</InputLabel>
          <Select
            value={value.preset}
            label="Time Period"
            onChange={(e) => handlePresetChange(e.target.value)}
          >
            <MenuItem value="last7days">Last 7 Days</MenuItem>
            <MenuItem value="last30days">Last 30 Days</MenuItem>
            <MenuItem value="last90days">Last 90 Days</MenuItem>
            <MenuItem value="custom">Custom Range</MenuItem>
          </Select>
        </FormControl>

        {value.preset === 'custom' && (
          <>
            <DatePicker
              label="Start Date"
              value={value.startDate}
              onChange={(date) => onChange({
                ...value,
                startDate: date || undefined,
              })}
              slotProps={{
                textField: { size: 'small', sx: { minWidth: 150 } }
              }}
            />
            <DatePicker
              label="End Date"
              value={value.endDate}
              onChange={(date) => onChange({
                ...value,
                endDate: date || undefined,
              })}
              slotProps={{
                textField: { size: 'small', sx: { minWidth: 150 } }
              }}
            />
          </>
        )}

        {onRefresh && (
          <Button
            variant="outlined"
            size="small"
            startIcon={<Refresh />}
            onClick={onRefresh}
          >
            Refresh
          </Button>
        )}
      </Box>
    </LocalizationProvider>
  );
};

export default TimePeriodFilter;