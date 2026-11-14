import QtQuick

Gradient {
    id: root

    property bool selected: false
    property bool depressed: false

    GradientStop {
        position: 0
        color: root.depressed ? "#101a25" : root.selected ? "#122c43" : "#405667"
    }
    GradientStop {
        position: 0.22
        color: root.selected ? "#1b4565" : "#2d4152"
    }
    GradientStop {
        position: 0.65
        color: root.selected ? "#245a80" : "#253748"
    }
    GradientStop {
        position: 1
        color: root.depressed ? "#5c8199" : root.selected ? "#397498" : "#263b50"
    }
}
