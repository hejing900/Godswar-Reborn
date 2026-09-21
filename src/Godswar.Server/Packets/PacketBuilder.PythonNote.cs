using System.Buffers.Binary;
using Godswar.Server.Protocol;

namespace Godswar.Server.Packets;

internal static partial class PacketBuilder
{
    private const int PythonNotePacketLength = 137;
    private const int PythonNoteFieldLength = 64;
    private const int PythonNoteTextPartLength = PythonNoteFieldLength - 1;
    internal const int CenteredAnnouncementMaximumTextLength =
        PythonNoteTextPartLength * 2;
    private const int PythonNoteDirectTextType = 50;
    private const byte PythonNoteCenterChannel = 0;
    private const byte PythonNotePersonalChannel = 1;
    private const string CenteredRedTextPrefix = "|cFFFF0000";
    private const string CenteredGreenTextPrefix = "|cFF00FF00";
    private const string CenteredTextColorReset = "|cFFFFFFFF";
    internal const int CenteredRedAnnouncementMaximumTextLength =
        CenteredAnnouncementMaximumTextLength - 20;

    /// <summary>
    /// Centred proclamation rendered in green. Same channel and formatter as
    /// <see cref="CenteredRedAnnouncement"/>, only the ARGB markup differs.
    /// </summary>
    public static byte[] CenteredGreenAnnouncement(string message)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        if (message.Length > CenteredRedAnnouncementMaximumTextLength ||
            message.Any(static character => character is < ' ' or > '~') ||
            message.Contains("|c", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentOutOfRangeException(
                nameof(message),
                "Native coloured announcements require at most 106 printable ASCII characters without color markup.");
        }

        return CenteredAnnouncement(
            CenteredGreenTextPrefix + message + CenteredTextColorReset);
    }

    /// <summary>
    /// Uses the stock proclamation renderer's ARGB text markup. The message
    /// is plain printable ASCII; the reset keeps the next notice's color intact.
    /// </summary>
    public static byte[] CenteredRedAnnouncement(string message)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        if (message.Length > CenteredRedAnnouncementMaximumTextLength ||
            message.Any(static character => character is < ' ' or > '~') ||
            message.Contains("|c", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentOutOfRangeException(
                nameof(message),
                "Native red announcements require at most 106 printable ASCII characters without color markup.");
        }

        return CenteredAnnouncement(
            CenteredRedTextPrefix + message + CenteredTextColorReset);
    }

    /// <summary>Direct text in the same native game log as daily item gains, without changing the bag or opening a dialogue.</summary>
    public static byte[] PersonalGameLog(string message)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        if (message.Any(static character => character is < ' ' or > '~'))
        {
            throw new ArgumentOutOfRangeException(
                nameof(message),
                "Native game logs require printable ASCII text.");
        }

        var packet = CenteredAnnouncement(message);
        // SrvMsg.lua CHANNEL_PRESONAL calls AddPersonalMessage_UTF8(text,6,1).
        packet[8] = PythonNotePersonalChannel;
        return packet;
    }

    /// <summary>
    /// Uses the stock client's direct-text announcement formatter. Its two
    /// fixed strings are concatenated before the center-screen proclamation
    /// is rendered, so splitting here does not alter the visible text.
    /// </summary>
    public static byte[] CenteredAnnouncement(string message)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        if (message.Any(static character => character > sbyte.MaxValue) ||
            message.Length > CenteredAnnouncementMaximumTextLength)
        {
            throw new ArgumentOutOfRangeException(
                nameof(message),
                "Native centered announcements require at most 126 ASCII bytes.");
        }

        var packet = new byte[PythonNotePacketLength];
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet,
            checked((ushort)PythonNotePacketLength));
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet.AsSpan(2),
            Opcodes.PythonNote);
        BinaryPrimitives.WriteInt32LittleEndian(
            packet.AsSpan(4),
            PythonNoteDirectTextType);
        packet[8] = PythonNoteCenterChannel;

        var split = Math.Min(message.Length, PythonNoteTextPartLength);
        PacketText.WriteFixedAscii(
            packet.AsSpan(9, PythonNoteFieldLength),
            message[..split]);
        PacketText.WriteFixedAscii(
            packet.AsSpan(73, PythonNoteFieldLength),
            message[split..]);
        return packet;
    }
}
