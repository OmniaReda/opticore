import { FileSizePipe } from './file-size-pipe';

describe('FileSizePipe', () => {
  const pipe = new FileSizePipe();

  it('formats bytes with binary units', () => {
    expect(pipe.transform(0)).toBe('0 B');
    expect(pipe.transform(1023)).toBe('1023 B');
    expect(pipe.transform(1024)).toBe('1.0 KB');
    expect(pipe.transform(5 * 1024 * 1024 + 512 * 1024)).toBe('5.5 MB');
    expect(pipe.transform(3 * 1024 ** 4)).toBe('3072.0 GB'); // largest unit is GB
  });
});
